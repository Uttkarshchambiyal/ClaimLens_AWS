from decimal import Decimal
import json
from types import SimpleNamespace

import pytest

from claimlens.api import StepFunctionsOrchestrator, _actor, _analysis_view, _response, _tenant, handler
from claimlens.config import Settings
from claimlens.extraction import make_evidence
from claimlens.models import CheckStatus
from claimlens.repository import InMemoryRepository, TenantDenied
from claimlens.rules import check_patient_identity, check_supporting_reports, reconcile_bill
from claimlens.service import AnalysisService
from claimlens.workflow import _adapter_fields
from conftest import field


def test_api_preserves_fractional_coordinates_and_confidence():
    result = json.loads(_response(200, {"left": Decimal("0.61"), "confidence": Decimal("98.4"), "paise": Decimal("125000")})["body"])
    assert result == {"left": .61, "confidence": 98.4, "paise": 125000}


def test_step_function_payload_serializes_dynamodb_decimals():
    client = SimpleNamespace(start_execution=lambda **kwargs: setattr(client, "request", kwargs))
    orchestrator = StepFunctionsOrchestrator(client, "state-machine")
    orchestrator.start("anl_123", {"version": Decimal("1"), "confidence": Decimal("98.4")})
    assert json.loads(client.request["input"]) == {"version": 1, "confidence": 98.4}


def test_dynamodb_decimal_amounts_are_reconciled(consistent_fields):
    from dataclasses import replace
    fields = [replace(f, normalized_value=Decimal(f.normalized_value)) if f.name in {"line_item_amount", "invoice_total"} else f for f in consistent_fields]
    assert reconcile_bill(fields, Settings()).status == CheckStatus.PASS


def test_conflicting_totals_do_not_pass(consistent_fields):
    assert reconcile_bill(consistent_fields + [field("invoice_total", "9000", 900000, block="second-total")], Settings()).status == CheckStatus.INSUFFICIENT_EVIDENCE


def test_duplicate_identifiers_from_one_document_are_insufficient():
    fields = [field("patient_identifier", "same", block="p1"), field("patient_identifier", "same", block="p2")]
    assert check_patient_identity(fields).status == CheckStatus.INSUFFICIENT_EVIDENCE


def test_any_report_does_not_automatically_support_a_charge():
    check = check_supporting_reports([field("procedure_or_device_charge", "200", 20000)], {"BILL", "SUPPORTING_REPORT"})
    assert check.status == CheckStatus.INSUFFICIENT_EVIDENCE


def test_empty_extraction_does_not_claim_support_is_not_applicable():
    assert check_supporting_reports([], {"BILL"}).status == CheckStatus.INSUFFICIENT_EVIDENCE


@pytest.mark.parametrize("claims", [
    {"custom:tenant_id": "tenant-a", "token_use": "access"},
    {"custom:tenant_id": "../tenant-b", "token_use": "id"},
    {"custom:tenant_id": "", "token_use": "id"},
])
def test_invalid_tenant_claims_rejected(claims):
    with pytest.raises(TenantDenied):
        _tenant({"requestContext": {"authorizer": {"jwt": {"claims": claims}}}}, Settings())


def test_valid_id_token_tenant_claim():
    assert _tenant({"requestContext": {"authorizer": {"jwt": {"claims": {"token_use": "id", "custom:tenant_id": "tenant-a"}}}}}, Settings()) == "tenant-a"


def test_mutations_require_an_authenticated_reviewer_subject():
    with pytest.raises(TenantDenied):
        _actor({"requestContext": {"authorizer": {"jwt": {"claims": {"token_use": "id"}}}}})
    assert _actor({"requestContext": {"authorizer": {"jwt": {"claims": {"sub": "reviewer-123"}}}}}) == "reviewer-123"


def test_geometry_covers_all_cited_words():
    blocks = [{"Id": "a", "Page": 1, "Confidence": 99, "Geometry": {"BoundingBox": {"Left": .1, "Top": .2, "Width": .2, "Height": .03}}}, {"Id": "b", "Page": 1, "Confidence": 98, "Geometry": {"BoundingBox": {"Left": .4, "Top": .2, "Width": .1, "Height": .03}}}]
    evidence = make_evidence("doc", 1, 1, blocks, "Invoice total")
    assert evidence.geometry.width == pytest.approx(.4)
    assert evidence.confidence == 98


def test_invalid_model_output_keeps_deterministic_results(consistent_fields):
    repo = InMemoryRepository()
    repo.put_once("a", "ANALYSIS", "analysis", {"claimId": "claim", "status": "PROCESSING"})
    payload = {"findings": [{"checkId": "semantic.test", "title": "Invented", "summary": "Unsupported", "status": "PASS", "priority": "LOW", "evidenceIds": ["does-not-exist"]}]}
    result = AnalysisService(repo, Settings()).analyze_fields("a", "analysis", consistent_fields, {"BILL", "DISCHARGE_SUMMARY"}, payload)
    assert result["status"] == "COMPLETED_WITH_WARNINGS"
    assert result["findings"][0]["status"] == "PASS"
    assert result["findings"][-1]["status"] == "ERROR"


def test_retried_worker_preserves_completed_analysis(consistent_fields):
    repo = InMemoryRepository()
    repo.put_once("a", "ANALYSIS", "analysis", {"claimId": "claim", "status": "PROCESSING"})
    service = AnalysisService(repo, Settings())
    first = service.analyze_fields("a", "analysis", consistent_fields, {"BILL"}, semantic_error="OFFLINE")
    second = service.analyze_fields("a", "analysis", [], set(), semantic_error="OFFLINE")
    assert second["completedAt"] == first["completedAt"]
    assert second["findings"] == first["findings"]
    assert repo.get_for_tenant("a", "ANALYSIS_VERSION", "analysis#v1")


def test_corrections_require_real_evidence_and_preserve_source(consistent_fields):
    repo = InMemoryRepository()
    repo.put_once("a", "ANALYSIS", "analysis", {"claimId": "claim", "status": "PROCESSING"})
    service = AnalysisService(repo, Settings())
    service.analyze_fields("a", "analysis", consistent_fields, {"BILL"})
    with pytest.raises(ValueError, match="Unknown evidence"):
        service.correct_field("a", "analysis", "invented", "123", "k")
    evidence_id = consistent_fields[0].evidence.evidence_id
    correction = service.correct_field("a", "analysis", evidence_id, "1001.00", "k")
    assert service.correct_field("a", "analysis", evidence_id, "1001.00", "k") == correction
    assert repo.get_for_tenant("a", "ANALYSIS", "analysis")["evidence"][evidence_id]["excerpt"] == "1000.00"
    assert correction["actorId"] == "local-reviewer"
    assert len(repo.list_for_tenant("a", "CORRECTION", "analysis#")) == 1


def test_retention_is_attached_to_local_records():
    repo = InMemoryRepository(retention_days=7)
    record = repo.put_once("a", "CLAIM", "claim", {})
    assert record["expiresAt"] > 0
    with pytest.raises(ValueError, match="Retention"):
        InMemoryRepository(retention_days=0)


def test_identical_fingerprints_can_exist_in_separate_tenants():
    repo = InMemoryRepository()
    repo.put_once("a", "INVOICE_FINGERPRINT", "hash", {"analysisId": "one"})
    repo.put_once("b", "INVOICE_FINGERPRINT", "hash", {"analysisId": "two"})
    assert repo.get_for_tenant("a", "INVOICE_FINGERPRINT", "hash")["analysisId"] == "one"
    assert len(repo.list_for_tenant("b", "INVOICE_FINGERPRINT")) == 1


def test_same_key_different_documents_is_rejected():
    repo = InMemoryRepository()
    service = AnalysisService(repo, Settings())
    repo.put_once("a", "CLAIM", "claim", {})
    for doc_id in ("one", "two"):
        repo.put_once("a", "DOCUMENT", doc_id, {"claimId": "claim", "documentType": "BILL", "version": 1, "objectKey": doc_id})
    service.start_analysis("a", "claim", ["one"], "same-key")
    with pytest.raises(ValueError, match="different packet"):
        service.start_analysis("a", "claim", ["two"], "same-key")


@pytest.mark.parametrize("description", ["Room", "Total knee replacement"])
def test_textract_table_extracts_amounts_without_total_double_count(description):
    blocks = [{"Id": "table", "BlockType": "TABLE", "Relationships": [{"Type": "CHILD", "Ids": ["c11", "c12", "c21", "c22", "c31", "c32"]}]}]
    for row, texts in enumerate([["Description", "Amount"], [description, "1000.00"], ["Grand total", "1000.00"]], 1):
        for column, text in enumerate(texts, 1):
            cell_id = f"c{row}{column}"
            blocks += [{"Id": cell_id, "BlockType": "CELL", "RowIndex": row, "ColumnIndex": column, "Page": 1, "Relationships": [{"Type": "CHILD", "Ids": [cell_id + "w"]}]}, {"Id": cell_id + "w", "BlockType": "WORD", "Text": text, "Confidence": 98, "Page": 1}]
    fields = _adapter_fields(blocks)
    assert [(f["name"], f["value"]) for f in fields if f["name"] == "line_item_amount"] == [("line_item_amount", "1000.00")]
    if description == "Total knee replacement":
        assert next(f for f in fields if f["name"] == "billed_procedure")["value"] == "total knee replacement: 1000.00"


def test_api_denies_cross_tenant_document_and_lists_only_authorized(monkeypatch):
    import claimlens.api as api
    repo = InMemoryRepository()
    repo.put_once("a", "DOCUMENT", "private", {"claimId": "claim", "contentType": "application/pdf", "objectKey": "secret"})
    monkeypatch.setattr(api, "_aws_dependencies", lambda _: (SimpleNamespace(), repo, AnalysisService(repo, Settings())))
    event = {"rawPath": "/claims/claim/documents/private", "pathParameters": {"claimId": "claim", "documentId": "private"}, "requestContext": {"http": {"method": "GET"}, "authorizer": {"jwt": {"claims": {"token_use": "id", "custom:tenant_id": "b"}}}}}
    assert handler(event, None)["statusCode"] == 403
    event["rawPath"] = "/analyses"
    assert json.loads(handler(event, None)["body"])["analyses"] == []
