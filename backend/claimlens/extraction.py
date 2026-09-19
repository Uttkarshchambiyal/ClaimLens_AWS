from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from hashlib import sha256
from typing import Any

from .config import Settings
from .models import EvidenceRef, ExtractedField, Geometry, evidence_to_dict
from .money import parse_money_to_paise


MONEY_FIELDS = {
    "invoice_total",
    "amount_paid",
    "balance_due",
    "claimed_amount",
    "line_item_amount",
    "invoice_adjustment",
    "procedure_or_device_charge",
}
DATE_FIELDS = {"admission_date", "discharge_date", "procedure_date"}


def _geometry(block: dict[str, Any]) -> Geometry:
    box = block.get("Geometry", {}).get("BoundingBox", {})
    if not all(name in box for name in ("Left", "Top", "Width", "Height")):
        raise ValueError("Source geometry is missing; no coordinates were fabricated")
    return Geometry(float(box["Left"]), float(box["Top"]), float(box["Width"]), float(box["Height"]))


def make_evidence(document_id: str, document_version: int, page: int, blocks: list[dict[str, Any]], excerpt: str) -> EvidenceRef:
    if not blocks:
        raise ValueError("An extracted field must cite at least one Textract block")
    blocks = list({block["Id"]: block for block in blocks}.values())
    block_ids = tuple(str(block["Id"]) for block in blocks)
    if any(int(block.get("Page", page)) != page for block in blocks):
        raise ValueError("An evidence region must belong to one source page")
    boxes = [_geometry(block) for block in blocks]
    left = min(box.left for box in boxes)
    top = min(box.top for box in boxes)
    geometry = Geometry(left, top, max(box.left + box.width for box in boxes) - left, max(box.top + box.height for box in boxes) - top)
    confidence = min(float(block.get("Confidence", 0)) for block in blocks)
    evidence_id = "ev_" + sha256(f"{document_id}|{document_version}|{page}|{'|'.join(block_ids)}".encode()).hexdigest()[:18]
    return EvidenceRef(evidence_id, document_id, document_version, page, block_ids, geometry, confidence, excerpt[:240])


def normalize_field(name: str, raw_value: Any, settings: Settings) -> tuple[Any, str]:
    if name in MONEY_FIELDS:
        parsed = parse_money_to_paise(raw_value, settings.decimal_rounding)
        return parsed.paise, parsed.status
    if name in DATE_FIELDS:
        text = str(raw_value).strip()
        patterns = ["%Y-%m-%d"]
        if settings.date_order == "DMY": patterns += ["%d/%m/%Y", "%d-%m-%Y"]
        elif settings.date_order == "MDY": patterns += ["%m/%d/%Y", "%m-%d-%Y"]
        for pattern in patterns:
            try:
                return datetime.strptime(text, pattern).date().isoformat(), "NORMALIZED"
            except ValueError:
                continue
        return None, "AMBIGUOUS"
    return str(raw_value).strip(), "NORMALIZED" if str(raw_value).strip() else "INVALID"


def fields_from_adapter(document_id: str, version: int, adapter_fields: list[dict[str, Any]], settings: Settings) -> tuple[list[ExtractedField], dict[str, EvidenceRef]]:
    fields: list[ExtractedField] = []
    evidence: dict[str, EvidenceRef] = {}
    for item in adapter_fields:
        blocks = item.get("blocks") or []
        ref = make_evidence(document_id, version, int(item.get("page", 1)), blocks, str(item.get("value", "")))
        normalized, status = normalize_field(str(item["name"]), item.get("value"), settings)
        if ref.confidence < settings.min_field_confidence and status == "NORMALIZED":
            status = "LOW_CONFIDENCE"
        field = ExtractedField(str(item["name"]), item.get("value"), normalized, ref, status)
        evidence[ref.evidence_id] = ref
        fields.append(field)
    return fields, evidence


def raw_textract_by_page(response_pages: list[dict[str, Any]]) -> dict[int, list[dict[str, Any]]]:
    result: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for response in response_pages:
        for block in response.get("Blocks", []):
            result[int(block.get("Page", 1))].append(block)
    return dict(result)


def serialize_extraction(fields: list[ExtractedField], evidence: dict[str, EvidenceRef]) -> dict[str, Any]:
    return {
        "normalizedFields": [{"name": field.name, "value": field.value, "normalizedValue": field.normalized_value, "normalizationStatus": field.normalization_status, "evidenceId": field.evidence.evidence_id} for field in fields],
        "evidence": {key: evidence_to_dict(value) for key, value in evidence.items()},
    }
