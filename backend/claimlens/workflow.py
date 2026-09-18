from __future__ import annotations

from dataclasses import asdict
from hashlib import sha256
import json
import os
import re
from typing import Any

from .config import Settings
from .extraction import fields_from_adapter, serialize_extraction
from .models import EvidenceRef, ExtractedField, Geometry
from .repository import DynamoRepository
from .semantic import BedrockAdapter
from .service import AnalysisService


LABELS = {
    "invoice total": "invoice_total", "grand total": "invoice_total", "amount paid": "amount_paid",
    "balance due": "balance_due", "claimed amount": "claimed_amount", "invoice number": "invoice_number",
    "bill number": "invoice_number", "provider id": "provider_identifier", "hospital id": "provider_identifier",
    "patient id": "patient_identifier", "member id": "patient_identifier", "admission date": "admission_date",
    "discharge date": "discharge_date", "procedure date": "procedure_date",
}


def _clients(settings: Settings):
    import boto3
    return {
        "textract": boto3.client("textract", region_name=settings.aws_region),
        "s3": boto3.client("s3", region_name=settings.aws_region),
        "bedrock": boto3.client("bedrock-runtime", region_name=settings.aws_region),
        "repo": DynamoRepository(boto3.resource("dynamodb", region_name=settings.aws_region).Table(settings.records_table), settings.retention_days),
    }


def _related_text(block: dict[str, Any], by_id: dict[str, dict[str, Any]], relation_type: str) -> tuple[str, list[dict[str, Any]]]:
    linked: list[dict[str, Any]] = []
    for relation in block.get("Relationships", []):
        if relation.get("Type") == relation_type:
            linked.extend(by_id[item] for item in relation.get("Ids", []) if item in by_id)
    words = []
    expanded: list[dict[str, Any]] = []
    for item in linked:
        expanded.append(item)
        if item.get("BlockType") == "WORD": words.append(item.get("Text", ""))
        else:
            text, children = _related_text(item, by_id, "CHILD")
            words.append(text); expanded.extend(children)
    return " ".join(filter(None, words)).strip(), expanded or linked


def _adapter_fields(blocks: list[dict[str, Any]], document_type: str = "BILL") -> list[dict[str, Any]]:
    by_id = {block["Id"]: block for block in blocks if block.get("Id")}
    fields: list[dict[str, Any]] = []
    for block in blocks:
        if block.get("BlockType") != "KEY_VALUE_SET" or "KEY" not in block.get("EntityTypes", []): continue
        label, _ = _related_text(block, by_id, "CHILD")
        canonical = LABELS.get(label.casefold().strip(" :"))
        if not canonical: continue
        value_blocks = []
        for relation in block.get("Relationships", []):
            if relation.get("Type") == "VALUE": value_blocks.extend(by_id[value_id] for value_id in relation.get("Ids", []) if value_id in by_id)
        if not value_blocks: continue
        value, expanded = _related_text(value_blocks[0], by_id, "CHILD")
        source = expanded or value_blocks
        fields.append({"name": canonical, "value": value, "page": int(value_blocks[0].get("Page", 1)), "blocks": source})
    # Only use tables with an explicit amount header. Never infer a monetary
    # column from position, and never count summary rows as line items.
    for table in (block for block in blocks if block.get("BlockType") == "TABLE"):
        cell_ids = [cell_id for relation in table.get("Relationships", []) if relation.get("Type") == "CHILD" for cell_id in relation.get("Ids", [])]
        cells = [by_id[cell_id] for cell_id in cell_ids if cell_id in by_id and by_id[cell_id].get("BlockType") == "CELL"]
        rows = {}
        for cell in cells:
            value, words = _related_text(cell, by_id, "CHILD")
            rows.setdefault(cell["RowIndex"], {})[cell["ColumnIndex"]] = (value, words, cell)
        amount_columns = []
        header_row = None
        for row_number in sorted(rows):
            for column, (value, _, _) in rows[row_number].items():
                if value.casefold().strip() in {"amount", "amount (inr)", "amount (rs)", "total amount", "net amount"}:
                    amount_columns.append(column)
                    header_row = row_number
            if amount_columns: break
        if len(amount_columns) != 1: continue
        amount_column = amount_columns[0]
        for row_number in sorted(rows):
            if row_number <= header_row or amount_column not in rows[row_number]: continue
            row = rows[row_number]
            description = " ".join(value for col, (value, _, _) in row.items() if col != amount_column).casefold()
            if re.fullmatch(r"(?:grand total|sub ?total|total|invoice total|net total|amount paid|balance(?: due)?)[\s:.-]*", description.strip()) or any(term in description for term in ("round off", "rounding", "discount", "tax", "gst")):
                # Adjustment rows require explicit normalization; do not guess.
                if any(term in description for term in ("discount", "tax", "gst", "round off", "rounding")):
                    value, words, cell = row[amount_column]
                    fields.append({"name": "line_item_amount", "value": "UNRESOLVED ADJUSTMENT: " + value, "page": int(cell.get("Page", 1)), "blocks": words or [cell]})
                continue
            value, words, cell = row[amount_column]
            if not value.strip(): continue
            fields.append({"name": "line_item_amount", "value": value, "page": int(cell.get("Page", 1)), "blocks": words or [cell]})
            if any(term in description for term in ("implant", "procedure", "surgery", "mri", "ct scan", "replacement")):
                fields.append({"name": "procedure_or_device_charge", "value": value, "page": int(cell.get("Page", 1)), "blocks": words or [cell]})
                source_blocks = [b for _, row_words, row_cell in row.values() for b in (row_words or [row_cell])]
                fields.append({"name": "billed_procedure", "value": description + ": " + value, "page": int(cell.get("Page", 1)), "blocks": source_blocks})
    if document_type in {"DISCHARGE_SUMMARY", "SUPPORTING_REPORT"}:
        # Bounded, cited prose for semantic comparison; raw full extraction stays in S3.
        for block in [b for b in blocks if b.get("BlockType") == "LINE" and b.get("Text", "").strip()][:40]:
            fields.append({"name": "clinical_statement", "value": block["Text"][:240], "page": int(block.get("Page", 1)), "blocks": [block]})
    return fields


def start_extraction_handler(event, _context):
    settings = Settings(); clients = _clients(settings); repo = clients["repo"]
    tenant, document_id = event["tenantId"], event["documentId"]
    document = repo.get_for_tenant(tenant, "DOCUMENT", document_id)
    if document["claimId"] != event["claimId"]: raise ValueError("Document claim mismatch")
    current = repo.get_for_tenant(tenant, "ANALYSIS", event["analysisId"])
    if current.get("completedAt"):
        return {**event, "jobId": document.get("textractJobId", ""), "jobStatus": document.get("extractionStatus", "FAILED")}
    repo.update_for_tenant(tenant, "ANALYSIS", event["analysisId"], {"status": "PROCESSING"})
    if document.get("textractJobId"):
        return {**event, "jobId": document["textractJobId"], "jobStatus": document.get("extractionStatus", "IN_PROGRESS")}
    token = sha256(f"{tenant}|{document_id}|{document['version']}".encode()).hexdigest()
    source = {"Bucket": settings.documents_bucket, "Name": document["objectKey"]}
    if document.get("s3VersionId"): source["Version"] = document["s3VersionId"]
    response = clients["textract"].start_document_analysis(DocumentLocation={"S3Object": source}, FeatureTypes=["FORMS", "TABLES"], JobTag=f"claimlens-{document_id}"[:64], ClientRequestToken=token)
    repo.update_for_tenant(tenant, "DOCUMENT", document_id, {"textractJobId": response["JobId"], "extractionStatus": "IN_PROGRESS", "status": "EXTRACTING"})
    return {**event, "jobId": response["JobId"], "jobStatus": "IN_PROGRESS"}


def poll_extraction_handler(event, _context):
    settings = Settings(); clients = _clients(settings); repo = clients["repo"]
    document = repo.get_for_tenant(event["tenantId"], "DOCUMENT", event["documentId"])
    if document["claimId"] != event["claimId"] or document.get("textractJobId") != event["jobId"]:
        raise ValueError("Extraction job does not belong to this document")
    if document.get("extractionStatus") in {"SUCCEEDED", "PARTIAL_SUCCESS", "FAILED"}:
        return {**event, "jobStatus": document["extractionStatus"]}
    response = clients["textract"].get_document_analysis(JobId=event["jobId"])
    status = response["JobStatus"]
    if status == "IN_PROGRESS": return {**event, "jobStatus": status}
    if status not in {"SUCCEEDED", "PARTIAL_SUCCESS"}:
        repo.update_for_tenant(event["tenantId"], "DOCUMENT", event["documentId"], {"extractionStatus": "FAILED", "status": "FAILED", "failureCategory": "TEXTRACT_JOB_FAILED"})
        return {**event, "jobStatus": "FAILED"}
    pages = [response]
    token = response.get("NextToken")
    while token:
        page = clients["textract"].get_document_analysis(JobId=event["jobId"], NextToken=token); pages.append(page); token = page.get("NextToken")
    raw_key = f"tenants/{event['tenantId']}/claims/{event['claimId']}/extractions/{event['documentId']}/v{event['version']}/textract.json"
    clients["s3"].put_object(Bucket=settings.documents_bucket, Key=raw_key, Body=json.dumps(pages).encode(), ContentType="application/json", ServerSideEncryption="AES256")
    blocks = [block for page in pages for block in page.get("Blocks", [])]
    fields, evidence = fields_from_adapter(event["documentId"], event["version"], _adapter_fields(blocks, event["documentType"]), settings)
    extraction = serialize_extraction(fields, evidence)
    serialized = json.dumps(extraction).encode()
    normalized_key = raw_key.replace("textract.json", "normalized.json")
    clients["s3"].put_object(Bucket=settings.documents_bucket, Key=normalized_key, Body=serialized, ContentType="application/json", ServerSideEncryption="AES256")
    if len(fields) > 120 or len(serialized) > 160000:
        repo.update_for_tenant(event["tenantId"], "DOCUMENT", event["documentId"], {"extractionStatus": "FAILED", "status": "FAILED", "rawExtractionKey": raw_key, "normalizedExtractionKey": normalized_key, "failureCategory": "EXTRACTION_LIMIT_EXCEEDED"})
        return {**event, "jobStatus": "FAILED"}
    quality = round(sum(ref.confidence for ref in evidence.values()) / len(evidence), 1) if evidence else 0
    repo.update_for_tenant(event["tenantId"], "DOCUMENT", event["documentId"], {"extractionStatus": status, "status": "READY" if status == "SUCCEEDED" else "PARTIAL", "rawExtractionKey": raw_key, "normalizedExtractionKey": normalized_key, "normalizedFields": extraction["normalizedFields"], "evidence": extraction["evidence"], "extractionQuality": quality, "pages": response.get("DocumentMetadata", {}).get("Pages", 0)})
    return {**event, "jobStatus": status}


def _deserialize(document: dict[str, Any]) -> list[ExtractedField]:
    evidence = document.get("evidence", {})
    result = []
    for item in document.get("normalizedFields", []):
        raw = evidence[item["evidenceId"]]
        box = raw["geometry"]
        ref = EvidenceRef(raw["evidence_id"], raw["document_id"], int(raw["document_version"]), int(raw["page"]), tuple(raw["block_ids"]), Geometry(float(box["left"]), float(box["top"]), float(box["width"]), float(box["height"])), float(raw["confidence"]), raw["excerpt"])
        result.append(ExtractedField(item["name"], item["value"], item["normalizedValue"], ref, item["normalizationStatus"]))
    return result


def analyze_handler(event, _context):
    settings = Settings(); clients = _clients(settings); repo = clients["repo"]
    current = repo.get_for_tenant(event["tenantId"], "ANALYSIS", event["analysisId"])
    if current.get("completedAt"):
        return {**event, "analysisStatus": current["status"]}
    fields: list[ExtractedField] = []; document_types: set[str] = set(); failures = []
    for ref in event["documents"]:
        document = repo.get_for_tenant(event["tenantId"], "DOCUMENT", ref["documentId"])
        if document.get("extractionStatus") != "SUCCEEDED":
            failures.append(document["id"])
        else:
            document_types.add(document["documentType"])
            fields.extend(_deserialize(document))
    semantic_payload = None; semantic_error = None
    if len(json.dumps([asdict(f) for f in fields], default=str).encode()) > 220000:
        raise ValueError("Packet exceeds bounded review size; split it into smaller packets")
    if failures:
        semantic_error = "EXTRACTION_INCOMPLETE"
    elif settings.use_bedrock:
        bundle = [{"evidenceId": field.evidence.evidence_id, "documentType": next((ref["documentType"] for ref in event["documents"] if ref["documentId"] == field.evidence.document_id), "UNKNOWN"), "field": field.name, "value": field.normalized_value, "excerpt": field.evidence.excerpt} for field in fields]
        try: semantic_payload = BedrockAdapter(settings.bedrock_model_id, clients["bedrock"]).compare(bundle)
        except Exception as exc:
            print(json.dumps({"event": "semantic_comparison_failed", "analysisId": event["analysisId"], "errorType": exc.__class__.__name__}))
            semantic_error = "BEDROCK_UNAVAILABLE_OR_INVALID_OUTPUT"
    else:
        semantic_error = "BEDROCK_DISABLED"
    result = AnalysisService(repo, settings).analyze_fields(event["tenantId"], event["analysisId"], fields, document_types, semantic_payload, semantic_error)
    return {**event, "analysisStatus": result["status"]}


def mark_failed_handler(event, _context):
    settings = Settings(); clients = _clients(settings)
    tenant = event.get("tenantId"); analysis_id = event.get("analysisId")
    if tenant and analysis_id:
        current = clients["repo"].get_for_tenant(tenant, "ANALYSIS", analysis_id)
        if current.get("completedAt"):
            return {"analysisId": analysis_id, "status": current["status"]}
        clients["repo"].update_for_tenant(tenant, "ANALYSIS", analysis_id, {"status": "FAILED", "failureCategory": "WORKFLOW_FAILURE"})
        AnalysisService(clients["repo"], settings).analyze_fields(tenant, analysis_id, [], set(), semantic_error="WORKFLOW_FAILURE")
    return {"analysisId": analysis_id, "status": "FAILED"}
