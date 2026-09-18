"""AWS-shaped integration tests using Moto; these do not verify live AWS access."""
from dataclasses import replace
from decimal import Decimal
import json

import boto3
from moto import mock_aws
import pytest

from claimlens.config import Settings
from claimlens.repository import DynamoRepository, NotFound, RequestInProgress
from claimlens.service import AnalysisService


@pytest.fixture
def aws_records():
    with mock_aws():
        table = boto3.resource("dynamodb", region_name="us-east-1").create_table(
            TableName="claimlens-test",
            KeySchema=[{"AttributeName": "pk", "KeyType": "HASH"}, {"AttributeName": "sk", "KeyType": "RANGE"}],
            AttributeDefinitions=[{"AttributeName": "pk", "AttributeType": "S"}, {"AttributeName": "sk", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        yield DynamoRepository(table)


def test_dynamodb_preserves_decimals_and_tenant_boundaries(aws_records):
    repo = aws_records
    repo.put_once("a", "DOCUMENT", "doc", {"confidence": 98.7, "geometry": {"left": .125}})
    record = repo.get_for_tenant("a", "DOCUMENT", "doc")
    assert record["confidence"] == Decimal("98.7")
    assert record["geometry"]["left"] == Decimal(".125")
    assert int(record["expiresAt"]) > 0
    with pytest.raises(NotFound):
        repo.get_for_tenant("b", "DOCUMENT", "doc")
    assert repo.list_for_tenant("b", "DOCUMENT") == []


def test_dynamodb_duplicate_request_cannot_enter_active_producer(aws_records):
    calls = []

    def produce():
        calls.append("called")
        with pytest.raises(RequestInProgress):
            aws_records.idempotent("a", "create", "key", lambda: pytest.fail("duplicate executed"))
        return {"id": "one"}

    assert aws_records.idempotent("a", "create", "key", produce) == {"id": "one"}
    assert aws_records.idempotent("a", "create", "key", produce) == {"id": "one"}
    assert len(calls) == 1


def test_dynamodb_failed_producer_releases_lease_for_retry(aws_records):
    def fail():
        raise RuntimeError("synthetic outage")

    with pytest.raises(RuntimeError):
        aws_records.idempotent("a", "create", "key", fail)
    assert aws_records.idempotent("a", "create", "key", lambda: {"retried": True}) == {"retried": True}


def test_api_upload_version_review_and_report_with_emulated_aws(aws_records, monkeypatch, consistent_fields):
    import claimlens.api as api

    s3 = boto3.client("s3", region_name="us-east-1")
    s3.create_bucket(Bucket="claimlens-synthetic-test")
    s3.put_bucket_versioning(Bucket="claimlens-synthetic-test", VersioningConfiguration={"Status": "Enabled"})
    settings = Settings(aws_region="us-east-1", documents_bucket="claimlens-synthetic-test")
    starts = []

    class Orchestrator:
        def start(self, analysis_id, payload):
            starts.append((analysis_id, payload))

    service = AnalysisService(aws_records, settings, Orchestrator())
    monkeypatch.setattr(api, "Settings", lambda: settings)
    monkeypatch.setattr(api, "_aws_dependencies", lambda _: (boto3, aws_records, service))

    def request(method, path, data=None, params=None, key="key", tenant="a"):
        event = {"rawPath": path, "body": json.dumps(data or {}), "pathParameters": params or {},
                 "headers": {"idempotency-key": key}, "requestContext": {"http": {"method": method},
                 "authorizer": {"jwt": {"claims": {"token_use": "id", "sub": "reviewer-123", "custom:tenant_id": tenant}}}}}
        response = api.handler(event, None)
        return response["statusCode"], json.loads(response["body"])

    status, claim = request("POST", "/claims")
    assert status == 201
    claim_id = claim["claimId"]
    status, doc = request("POST", f"/claims/{claim_id}/documents/upload-request", {
        "filename": "synthetic.pdf", "contentType": "application/pdf", "documentType": "BILL",
    }, {"claimId": claim_id})
    assert status == 201 and doc["method"] == "POST"
    assert doc["uploadFields"]["x-amz-server-side-encryption"] == "AES256"
    assert doc["uploadFields"]["Content-Type"] == "application/pdf"
    upload = s3.put_object(Bucket=settings.documents_bucket, Key=doc["objectKey"], Body=b"synthetic fixture bytes",
                          ContentType="application/pdf", ServerSideEncryption="AES256")
    packet = {"claimId": claim_id, "documentIds": [doc["documentId"]]}
    status, started = request("POST", "/analyses", packet)
    assert status == 202
    assert request("POST", "/analyses", packet)[1] == started
    assert len(starts) == 1
    assert starts[0][1]["documents"][0]["s3VersionId"] == upload["VersionId"]
    # Normalized synthetic extraction is injected; Textract itself is NOT exercised.
    fields = [replace(field, evidence=replace(field.evidence, document_id=doc["documentId"]))
              for field in consistent_fields if field.evidence.document_id == "doc_bill"]
    analysis_id = started["analysisId"]
    result = service.analyze_fields("a", analysis_id, fields, {"BILL"}, semantic_error="OFFLINE")
    finding_id = result["findings"][0]["finding_id"]
    status, _ = request("PATCH", f"/analyses/{analysis_id}/findings/{finding_id}",
                        {"reviewerAction": "RESOLVED"}, {"analysisId": analysis_id, "findingId": finding_id})
    assert status == 200
    status, error = request("PATCH", f"/analyses/{analysis_id}/findings/{finding_id}",
                            {"reviewerAction": "OPEN"}, {"analysisId": analysis_id, "findingId": finding_id})
    assert status == 400 and error["error"] == "INVALID_REQUEST"
    status, _ = request("PATCH", f"/analyses/{analysis_id}/findings/{finding_id}",
                        {"reviewerAction": "ACKNOWLEDGED"}, {"analysisId": analysis_id, "findingId": finding_id}, key="action-2")
    assert status == 200
    status, report = request("GET", f"/analyses/{analysis_id}/report", params={"analysisId": analysis_id})
    assert status == 200
    assert report["analysis"]["findings"][0]["reviewerAction"] == "ACKNOWLEDGED"
    assert report["analysis"]["findings"][0]["evidence"][0]["geometry"]["left"] == .1
    assert report["analysis"]["activity"][0]["actorId"] == "reviewer-123"
    review_events = aws_records.list_for_tenant("a", "REVIEW_EVENT", analysis_id + "#")
    assert len(review_events) == 2
    assert any(event["previousReviewerAction"] == "RESOLVED" for event in review_events)
    status, _ = request("GET", f"/analyses/{analysis_id}", params={"analysisId": analysis_id}, tenant="b")
    assert status == 404
    assert request("GET", "/analyses", tenant="b")[1] == {"analyses": []}
