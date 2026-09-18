from __future__ import annotations

from dataclasses import asdict
from hashlib import sha256
import json
import uuid
from typing import Any, Protocol

from .config import Settings
from .models import CheckStatus, EvidenceRef, ExtractedField, Finding, Priority, evidence_to_dict, validate_finding_evidence
from .repository import ConditionalConflict, NotFound, now_iso
from .rules import invoice_fingerprint, run_deterministic_checks
from .semantic import validate_model_output


class Orchestrator(Protocol):
    def start(self, analysis_id: str, payload: dict[str, Any]) -> None: ...


class AnalysisService:
    def __init__(self, repository, settings: Settings, orchestrator: Orchestrator | None = None):
        self.repository = repository
        self.settings = settings
        self.orchestrator = orchestrator

    def create_claim(self, tenant_id: str, idempotency_key: str) -> dict[str, Any]:
        claim_id = "clm_" + sha256(f"{tenant_id}|create-claim|{idempotency_key}".encode()).hexdigest()[:18]
        def produce():
            self.repository.put_once(tenant_id, "CLAIM", claim_id, {"status": "DRAFT", "createdAt": now_iso(), "documentIds": []})
            return {"claimId": claim_id, "status": "DRAFT"}
        try:
            return self.repository.idempotent(tenant_id, "create-claim", idempotency_key, produce)
        except ConditionalConflict:
            return {"claimId": claim_id, "status": self.repository.get_for_tenant(tenant_id, "CLAIM", claim_id)["status"]}

    def register_document(self, tenant_id: str, claim_id: str, filename: str, content_type: str, document_type: str, idempotency_key: str) -> dict[str, Any]:
        self.repository.get_for_tenant(tenant_id, "CLAIM", claim_id)
        if content_type not in {"application/pdf", "image/png", "image/jpeg"}:
            raise ValueError("Unsupported document content type")
        if document_type not in {"BILL", "DISCHARGE_SUMMARY", "SUPPORTING_REPORT"}:
            raise ValueError("Unsupported document type")
        if not isinstance(filename, str) or not filename.strip() or len(filename) > 180:
            raise ValueError("A filename of 1 to 180 characters is required")
        document_id = "doc_" + sha256(f"{tenant_id}|{claim_id}|register-document|{idempotency_key}".encode()).hexdigest()[:18]
        try:
            existing = self.repository.get_for_tenant(tenant_id, "DOCUMENT", document_id)
            if (existing["filename"], existing["contentType"], existing["documentType"]) != (filename, content_type, document_type):
                raise ValueError("Idempotency key was already used for a different document")
        except NotFound:
            pass
        def produce():
            version = 1
            safe_suffix = {"application/pdf": ".pdf", "image/png": ".png", "image/jpeg": ".jpg"}[content_type]
            object_key = f"tenants/{tenant_id}/claims/{claim_id}/documents/{document_id}/v{version}/source{safe_suffix}"
            self.repository.put_once(tenant_id, "DOCUMENT", document_id, {"claimId": claim_id, "filename": filename[:180], "contentType": content_type, "documentType": document_type, "version": version, "objectKey": object_key, "status": "AWAITING_UPLOAD", "createdAt": now_iso()})
            return {"documentId": document_id, "version": version, "objectKey": object_key}
        try:
            return self.repository.idempotent(tenant_id, f"register-document#{claim_id}", idempotency_key, produce)
        except ConditionalConflict:
            existing = self.repository.get_for_tenant(tenant_id, "DOCUMENT", document_id)
            return {"documentId": document_id, "version": existing["version"], "objectKey": existing["objectKey"]}

    def start_analysis(self, tenant_id: str, claim_id: str, document_ids: list[str], idempotency_key: str) -> dict[str, Any]:
        self.repository.get_for_tenant(tenant_id, "CLAIM", claim_id)
        if not isinstance(document_ids, list) or not 1 <= len(document_ids) <= 10 or len(set(document_ids)) != len(document_ids):
            raise ValueError("Provide 1 to 10 distinct document identifiers")
        documents = [self.repository.get_for_tenant(tenant_id, "DOCUMENT", doc_id) for doc_id in document_ids]
        if any(document["claimId"] != claim_id for document in documents):
            raise ValueError("Every document must belong to the requested claim")
        if sum(doc["documentType"] == "BILL" for doc in documents) != 1:
            raise ValueError("Exactly one bill is required per analysis")
        analysis_id = "anl_" + sha256(f"{tenant_id}|{claim_id}|start-analysis|{idempotency_key}".encode()).hexdigest()[:18]
        payload = {"tenantId": tenant_id, "claimId": claim_id, "analysisId": analysis_id, "documents": [{"documentId": doc["id"], "version": doc["version"], "documentType": doc["documentType"], "objectKey": doc["objectKey"], "s3VersionId": doc.get("s3VersionId")} for doc in documents]}
        try:
            existing = self.repository.get_for_tenant(tenant_id, "ANALYSIS", analysis_id)
            if existing["documentIds"] != document_ids: raise ValueError("Idempotency key was already used for a different packet")
        except NotFound:
            pass
        def produce():
            self.repository.put_once(tenant_id, "ANALYSIS", analysis_id, {"claimId": claim_id, "status": "QUEUED", "analysisVersion": 1, "documentIds": document_ids, "createdAt": now_iso()})
            if self.orchestrator:
                self.orchestrator.start(analysis_id, payload)
            return {"analysisId": analysis_id, "status": "QUEUED"}
        try:
            return self.repository.idempotent(tenant_id, f"start-analysis#{claim_id}", idempotency_key, produce)
        except ConditionalConflict:
            if self.orchestrator:
                self.orchestrator.start(analysis_id, payload)
            existing = self.repository.get_for_tenant(tenant_id, "ANALYSIS", analysis_id)
            return {"analysisId": analysis_id, "status": existing["status"]}

    def analyze_fields(self, tenant_id: str, analysis_id: str, fields: list[ExtractedField], document_types: set[str], semantic_payload: dict[str, Any] | None = None, semantic_error: str | None = None) -> dict[str, Any]:
        analysis = self.repository.get_for_tenant(tenant_id, "ANALYSIS", analysis_id)
        if analysis.get("completedAt"):
            return analysis
        evidence: dict[str, EvidenceRef] = {field.evidence.evidence_id: field.evidence for field in fields}
        fingerprint = invoice_fingerprint(fields)
        historical = set()
        if fingerprint:
            try:
                prior = self.repository.get_for_tenant(tenant_id, "INVOICE_FINGERPRINT", fingerprint)
                if prior.get("analysisId") != analysis_id:
                    historical.add(fingerprint)
            except NotFound:
                pass
        findings = run_deterministic_checks(fields, document_types, self.settings, historical)
        if semantic_payload is not None:
            try:
                model_findings = validate_model_output(semantic_payload, evidence)
                if not model_findings: raise ValueError("Empty comparison response")
                findings.extend(model_findings)
            except (ValueError, TypeError, KeyError):
                semantic_error = "INVALID_MODEL_OUTPUT"
        if semantic_error:
            error_id = "f_" + sha256(f"semantic-error|{analysis_id}".encode()).hexdigest()[:14]
            findings.append(Finding(error_id, "semantic.comparison", "Semantic comparison unavailable", "The bounded semantic comparison could not run. No clean result was inferred from this failure.", CheckStatus.ERROR, Priority.MEDIUM, [], source="SYSTEM"))
        for finding in findings:
            validate_finding_evidence(finding, evidence)
        review_priority = "HIGH" if any(f.priority == Priority.HIGH and f.status == CheckStatus.FINDING for f in findings) else "MEDIUM" if any(f.status in (CheckStatus.FINDING, CheckStatus.INSUFFICIENT_EVIDENCE, CheckStatus.ERROR) for f in findings) else "LOW"
        extraction_quality = round(sum(item.evidence.confidence for item in fields) / len(fields), 1) if fields else 0
        complete = sum(f.status in (CheckStatus.PASS, CheckStatus.FINDING, CheckStatus.NOT_APPLICABLE) for f in findings)
        coverage = round(100 * complete / len(findings)) if findings else 0
        status = "COMPLETED_WITH_WARNINGS" if any(f.status in (CheckStatus.INSUFFICIENT_EVIDENCE, CheckStatus.ERROR) for f in findings) else "COMPLETED"
        if analysis.get("status") == "FAILED": status = "FAILED"
        claimed = [field.normalized_value for field in fields if field.name == "claimed_amount" and field.normalization_status == "NORMALIZED"]
        result = {**analysis, "status": status, "reviewPriority": review_priority, "extractionQuality": extraction_quality, "coverage": coverage, "findings": [f.to_dict() for f in findings], "evidence": {key: evidence_to_dict(ref) for key, ref in evidence.items()}, "completedAt": now_iso(), "claimedAmountPaise": int(claimed[0]) if len(claimed) == 1 and claimed[0] is not None else None}
        try:
            self.repository.put_once(tenant_id, "ANALYSIS_VERSION", analysis_id + "#v" + str(analysis.get("analysisVersion", 1)), result)
        except ConditionalConflict:
            result = self.repository.get_for_tenant(tenant_id, "ANALYSIS_VERSION", analysis_id + "#v" + str(analysis.get("analysisVersion", 1)))
        self.repository.update_for_tenant(tenant_id, "ANALYSIS", analysis_id, {key: result[key] for key in ("status", "reviewPriority", "extractionQuality", "coverage", "findings", "evidence", "completedAt", "claimedAmountPaise")})
        if fingerprint:
            try:
                self.repository.put_once(tenant_id, "INVOICE_FINGERPRINT", fingerprint, {"analysisId": analysis_id, "createdAt": now_iso()})
            except ConditionalConflict:
                pass
        return result

    def correct_field(self, tenant_id: str, analysis_id: str, field_id: str, new_value: Any, idempotency_key: str, actor_id: str = "local-reviewer") -> dict[str, Any]:
        analysis = self.repository.get_for_tenant(tenant_id, "ANALYSIS", analysis_id)
        if field_id not in analysis.get("evidence", {}): raise ValueError("Unknown evidence reference")
        if not isinstance(new_value, str) or not 1 <= len(new_value.strip()) <= 500: raise ValueError("Correction must contain 1 to 500 characters")
        correction_id = analysis_id + "#" + sha256(idempotency_key.encode()).hexdigest()[:18]
        try:
            existing = self.repository.get_for_tenant(tenant_id, "CORRECTION", correction_id)
            if existing["correctedValue"] != new_value or existing["fieldId"] != field_id or existing.get("actorId") != actor_id:
                raise ValueError("Idempotency key was already used for a different correction")
        except NotFound:
            pass
        def produce():
            value = {"analysisId": analysis_id, "fieldId": field_id, "correctedValue": new_value, "basedOnAnalysisVersion": self.repository.get_for_tenant(tenant_id, "ANALYSIS", analysis_id).get("analysisVersion", 1), "actorId": actor_id, "createdAt": now_iso(), "preservesSourceExtraction": True}
            try: self.repository.put_once(tenant_id, "CORRECTION", correction_id, value)
            except ConditionalConflict: return self.repository.get_for_tenant(tenant_id, "CORRECTION", correction_id)
            return {"correctionId": correction_id, **value}
        return self.repository.idempotent(tenant_id, f"correct-field#{analysis_id}#{field_id}", idempotency_key, produce)
