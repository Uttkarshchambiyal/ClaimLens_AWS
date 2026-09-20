from __future__ import annotations

from decimal import Decimal
import base64
from hashlib import sha256
import json
import os
import re
from typing import Any

from .config import Settings, require_production
from .repository import DynamoRepository, NotFound, RequestInProgress, TenantDenied
from .service import AnalysisService


def _json_default(value: Any):
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral_value() else float(value)
    raise TypeError(f"Object of type {value.__class__.__name__} is not JSON serializable")


class StepFunctionsOrchestrator:
    def __init__(self, client, arn: str): self.client, self.arn = client, arn
    def start(self, analysis_id: str, payload: dict[str, Any]) -> None:
        try:
            self.client.start_execution(stateMachineArn=self.arn, name=analysis_id.replace("_", "-")[:80], input=json.dumps(payload, default=_json_default))
        except Exception as exc:
            if exc.__class__.__name__ != "ExecutionAlreadyExists":
                raise


def _aws_dependencies(settings: Settings):
    require_production(settings)
    import boto3
    dynamodb = boto3.resource("dynamodb", region_name=settings.aws_region)
    repo = DynamoRepository(dynamodb.Table(settings.records_table), settings.retention_days)
    return boto3, repo, AnalysisService(repo, settings, StepFunctionsOrchestrator(boto3.client("stepfunctions", region_name=settings.aws_region), settings.state_machine_arn))


def _response(status: int, body: Any):
    return {"statusCode": status, "headers": {"Content-Type": "application/json", "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff", "Access-Control-Allow-Origin": os.getenv("ALLOWED_ORIGIN", "")}, "body": json.dumps(body, default=_json_default)}


def _tenant(event: dict[str, Any], settings: Settings) -> str:
    claims = event.get("requestContext", {}).get("authorizer", {}).get("jwt", {}).get("claims", {})
    tenant = claims.get(settings.tenant_claim)
    if claims.get("token_use") != "id" or not isinstance(tenant, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", tenant):
        raise TenantDenied("A valid tenant claim is required")
    return tenant


def _actor(event: dict[str, Any]) -> str:
    claims = event.get("requestContext", {}).get("authorizer", {}).get("jwt", {}).get("claims", {})
    actor = claims.get("sub")
    if not isinstance(actor, str) or not re.fullmatch(r"[A-Za-z0-9._:@+-]{1,128}", actor):
        raise TenantDenied("A valid authenticated reviewer subject is required")
    return actor


def _body(event: dict[str, Any]) -> dict[str, Any]:
    raw = event.get("body") or "{}"
    if event.get("isBase64Encoded"):
        raw = base64.b64decode(raw).decode()
    value = json.loads(raw)
    if not isinstance(value, dict): raise ValueError("JSON body must be an object")
    return value


def _analysis_view(repo, tenant: str, analysis: dict[str, Any]) -> dict[str, Any]:
    evidence = analysis.get("evidence", {})
    documents_by_id = {doc_id: repo.get_for_tenant(tenant, "DOCUMENT", doc_id) for doc_id in analysis.get("documentIds", [])}
    reviews = repo.list_for_tenant(tenant, "REVIEW", analysis["id"] + "#")
    review_events = repo.list_for_tenant(tenant, "REVIEW_EVENT", analysis["id"] + "#")
    review_actions = {item["findingId"]: item for item in reviews}
    corrections = repo.list_for_tenant(tenant, "CORRECTION", analysis["id"] + "#")
    findings = []
    for item in analysis.get("findings", []):
        findings.append({
            "id": item["finding_id"], "checkId": item["check_id"], "title": item["title"], "summary": item["summary"],
            "status": item["status"], "priority": item["priority"], "requestedEvidence": item.get("requested_evidence"),
            "reviewerAction": review_actions.get(item["finding_id"], {}).get("reviewerAction", item.get("reviewerAction", "OPEN")),
            "evidence": [{
                "evidenceId": raw["evidence_id"], "documentId": raw["document_id"], "documentVersion": raw["document_version"], "documentName": documents_by_id.get(raw["document_id"], {}).get("filename", raw["document_id"]),
                "page": raw["page"], "blockIds": raw["block_ids"], "geometry": raw["geometry"], "confidence": raw["confidence"], "excerpt": raw["excerpt"],
            } for ref in item.get("evidence_ids", []) if (raw := evidence.get(ref))],
        })
    documents = []
    for document_id in analysis.get("documentIds", []):
        document = documents_by_id[document_id]
        documents.append({"id": document_id, "name": document["filename"], "type": document["documentType"], "version": document["version"], "pages": document.get("pages", 0), "extractionQuality": document.get("extractionQuality"), "status": document.get("status", "EXTRACTING")})
    return {
        "id": analysis["id"], "claimId": analysis["claimId"], "status": analysis["status"], "analysisVersion": analysis.get("analysisVersion", 1),
        "reviewPriority": analysis.get("reviewPriority", "MEDIUM"), "extractionQuality": analysis.get("extractionQuality", 0), "coverage": analysis.get("coverage", 0),
        "createdAt": analysis["createdAt"], "claimedAmountPaise": analysis.get("claimedAmountPaise"), "findings": findings, "documents": documents,
        "corrections": [{**row, "correctionId": row.get("correctionId", row["id"])} for row in corrections],
        "activity": sorted(
            [{"id": row["id"], "title": "Review disposition: " + row["reviewerAction"].lower(), "detail": row["findingId"], "at": row["createdAt"], "actorId": row.get("actorId")} for row in review_events]
            + [{"id": row["id"], "title": "Extraction correction recorded", "detail": "Original preserved. Checks have not been rerun.", "at": row["createdAt"], "actorId": row.get("actorId")} for row in corrections],
            key=lambda row: row["at"],
        ),
    }


def _assistant_reply(repo, tenant: str, message: str, analysis_id: str | None) -> dict[str, Any]:
    """Return a deterministic, evidence-linked reviewer aid without using document text as instructions."""
    message_words = set(re.findall(r"[a-z0-9]{3,}", message.lower()))
    analyses = sorted(repo.list_for_tenant(tenant, "ANALYSIS"), key=lambda row: row["createdAt"], reverse=True)
    if analysis_id:
        analysis = repo.get_for_tenant(tenant, "ANALYSIS", analysis_id)
    elif analyses:
        analysis = analyses[0]
    else:
        return {
            "answer": "There are no claim packets in this workspace yet. Upload a packet to review its findings and evidence.",
            "sources": [],
        }

    view = _analysis_view(repo, tenant, analysis)
    findings = [item for item in view["findings"] if item["status"] != "PASS"]
    matched = [
        item for item in findings
        if message_words.intersection(set(re.findall(r"[a-z0-9]{3,}", (item["title"] + " " + item["summary"]).lower())))
    ]
    selected = (matched or findings)[:2]
    if not selected:
        return {
            "answer": f"{view['claimId']} has no open review findings. Inspect the source documents before recording a final reviewer action.",
            "sources": [],
        }
    sources = [
        {"documentName": evidence["documentName"], "page": evidence["page"], "excerpt": evidence["excerpt"]}
        for finding in selected for evidence in finding["evidence"]
    ][:4]
    detail = "\n".join(f"• {item['title']}: {item['summary']}" for item in selected)
    citations = "; ".join(f"{item['documentName']}, page {item['page']}" for item in sources)
    return {
        "answer": f"Review context for {view['claimId']}:\n\n{detail}\n\nEvidence: {citations or 'No source citation is available.'}\n\nUse the source viewer to verify the cited fields before acknowledging or resolving a finding. ClaimLens does not approve, deny, or adjudicate claims.",
        "sources": sources,
    }


def handler(event, _context):
    settings = Settings()
    try:
        tenant = _tenant(event, settings)
        boto3, repo, service = _aws_dependencies(settings)
        method = event.get("requestContext", {}).get("http", {}).get("method", event.get("httpMethod", ""))
        path = event.get("rawPath", event.get("path", ""))
        params = event.get("pathParameters") or {}
        idem = (event.get("headers") or {}).get("idempotency-key") or (event.get("headers") or {}).get("Idempotency-Key")
        if method in {"POST", "PATCH"} and path != "/assistant/chat" and not idem:
            return _response(400, {"error": "IDEMPOTENCY_KEY_REQUIRED"})
        if idem and (not isinstance(idem, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", idem)):
            raise ValueError("Invalid idempotency key")
        if method == "POST" and path == "/assistant/chat":
            data = _body(event)
            message = data.get("message")
            analysis_id = data.get("analysisId")
            if not isinstance(message, str) or not message.strip() or len(message) > 2000:
                raise ValueError("Message must be between 1 and 2000 characters")
            if analysis_id is not None and (not isinstance(analysis_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", analysis_id)):
                raise ValueError("Invalid analysis identifier")
            return _response(200, _assistant_reply(repo, tenant, message, analysis_id))
        if method == "POST" and path == "/claims":
            return _response(201, service.create_claim(tenant, idem))
        if method == "POST" and path.endswith("/documents/upload-request"):
            data = _body(event); claim_id = params["claimId"]
            record = service.register_document(tenant, claim_id, data["filename"], data["contentType"], data["documentType"], idem)
            upload = boto3.client("s3", region_name=settings.aws_region).generate_presigned_post(
                Bucket=settings.documents_bucket,
                Key=record["objectKey"],
                Fields={"Content-Type": data["contentType"], "x-amz-server-side-encryption": "AES256"},
                Conditions=[
                    {"Content-Type": data["contentType"]},
                    {"x-amz-server-side-encryption": "AES256"},
                    ["content-length-range", 1, 15 * 1024 * 1024],
                ],
                ExpiresIn=settings.upload_expiry_seconds,
            )
            return _response(201, {**record, "uploadUrl": upload["url"], "uploadFields": upload["fields"], "method": "POST", "expiresIn": settings.upload_expiry_seconds})
        if method == "POST" and path == "/analyses":
            data = _body(event)
            # Pin an uploaded S3 version before asynchronous work starts. An old PUT
            # URL cannot replace the source bytes used by a queued analysis.
            document_ids = data.get("documentIds", [])
            if not isinstance(document_ids, list) or not 1 <= len(document_ids) <= 10 or not all(isinstance(value, str) for value in document_ids):
                raise ValueError("A packet must have 1 to 10 document identifiers")
            for document_id in document_ids:
                document = repo.get_for_tenant(tenant, "DOCUMENT", document_id)
                if document["claimId"] != data["claimId"]: raise TenantDenied("Document does not belong to claim")
                if not document.get("s3VersionId"):
                    head = boto3.client("s3", region_name=settings.aws_region).head_object(Bucket=settings.documents_bucket, Key=document["objectKey"])
                    if not 0 < head["ContentLength"] <= 15 * 1024 * 1024 or head.get("ContentType") != document["contentType"]:
                        raise ValueError("Uploaded file size or content type is invalid")
                    repo.update_for_tenant(tenant, "DOCUMENT", document_id, {"s3VersionId": head["VersionId"], "status": "EXTRACTING"})
            return _response(202, service.start_analysis(tenant, data["claimId"], data.get("documentIds", []), idem))
        if method == "GET" and path == "/analyses":
            records = sorted(repo.list_for_tenant(tenant, "ANALYSIS"), key=lambda row: row["createdAt"], reverse=True)
            return _response(200, {"analyses": [_analysis_view(repo, tenant, record) for record in records]})
        if method == "GET" and path.endswith("/report"):
            analysis = repo.get_for_tenant(tenant, "ANALYSIS", params["analysisId"])
            from .repository import now_iso
            return _response(200, {"reportVersion": analysis.get("analysisVersion", 1), "generatedAt": now_iso(), "analysis": _analysis_view(repo, tenant, analysis), "disclaimer": "Human review required. This report does not adjudicate the claim. Corrections are annotations; automated results have not been recalculated."})
        if method == "GET" and path.startswith("/analyses/"):
            analysis = repo.get_for_tenant(tenant, "ANALYSIS", params["analysisId"])
            return _response(200, _analysis_view(repo, tenant, analysis))
        if method == "GET" and path.startswith("/claims/") and "/documents/" in path:
            document = repo.get_for_tenant(tenant, "DOCUMENT", params["documentId"])
            if document["claimId"] != params["claimId"]: raise TenantDenied("Document does not belong to claim")
            source_params = {"Bucket": settings.documents_bucket, "Key": document["objectKey"], "ResponseContentDisposition": "inline"}
            if document.get("s3VersionId"): source_params["VersionId"] = document["s3VersionId"]
            url = boto3.client("s3", region_name=settings.aws_region).generate_presigned_url("get_object", Params=source_params, ExpiresIn=300)
            return _response(200, {"documentId": document["id"], "contentType": document["contentType"], "downloadUrl": url})
        if method == "GET" and path.startswith("/claims/"):
            return _response(200, repo.get_for_tenant(tenant, "CLAIM", params["claimId"]))
        if method == "PATCH" and "/findings/" in path:
            analysis = repo.get_for_tenant(tenant, "ANALYSIS", params["analysisId"])
            data = _body(event); action = data.get("reviewerAction")
            if action not in {"OPEN", "ACKNOWLEDGED", "RESOLVED"}: raise ValueError("Invalid reviewer action")
            finding_id = params["findingId"]
            if not any(item["finding_id"] == finding_id for item in analysis.get("findings", [])): raise NotFound(finding_id)
            actor_id = _actor(event)
            event_id = params["analysisId"] + "#" + finding_id + "#" + sha256(idem.encode()).hexdigest()[:18]
            try:
                existing_event = repo.get_for_tenant(tenant, "REVIEW_EVENT", event_id)
                if existing_event.get("reviewerAction") != action or existing_event.get("actorId") != actor_id:
                    raise ValueError("Idempotency key was already used for a different review action")
            except NotFound:
                pass
            def save_action():
                from .repository import ConditionalConflict, now_iso
                record_id = params["analysisId"] + "#" + finding_id
                at = now_iso()
                try:
                    previous = repo.get_for_tenant(tenant, "REVIEW", record_id).get("reviewerAction", "OPEN")
                except NotFound:
                    previous = "OPEN"
                event_value = {"analysisId": params["analysisId"], "findingId": finding_id, "reviewerAction": action, "previousReviewerAction": previous, "actorId": actor_id, "createdAt": at}
                try: repo.put_once(tenant, "REVIEW_EVENT", event_id, event_value)
                except ConditionalConflict: pass
                value = {"findingId": finding_id, "reviewerAction": action, "actorId": actor_id, "updatedAt": at}
                try: repo.put_once(tenant, "REVIEW", record_id, value)
                except ConditionalConflict: repo.update_for_tenant(tenant, "REVIEW", record_id, value)
                return {"findingId": finding_id, "reviewerAction": action, "actorId": actor_id, "eventId": event_id}
            result = repo.idempotent(tenant, f"finding-action#{params['analysisId']}#{finding_id}", idem, save_action)
            return _response(200, result)
        if method == "PATCH" and path.endswith("/corrections"):
            data = _body(event)
            return _response(201, service.correct_field(tenant, params["analysisId"], data["fieldId"], data["correctedValue"], idem, _actor(event)))
        return _response(404, {"error": "NOT_FOUND"})
    except TenantDenied:
        return _response(403, {"error": "FORBIDDEN"})
    except RequestInProgress:
        return _response(409, {"error": "REQUEST_IN_PROGRESS", "message": "This request is already processing. Retry with the same idempotency key."})
    except NotFound:
        return _response(404, {"error": "NOT_FOUND"})
    except (KeyError, ValueError, json.JSONDecodeError) as exc:
        return _response(400, {"error": "INVALID_REQUEST", "message": str(exc)})
    except Exception as exc:
        # Never log document text or model input. Lambda captures only this category.
        print(json.dumps({"event": "api_error", "errorType": exc.__class__.__name__}))
        return _response(500, {"error": "INTERNAL_ERROR"})
