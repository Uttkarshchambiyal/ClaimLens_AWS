from __future__ import annotations

import pytest

from claimlens.models import EvidenceRef, ExtractedField, Geometry


def field(name, value, normalized=None, document_id="doc_bill", page=1, block="b1", confidence=98.0, status="NORMALIZED"):
    evidence = EvidenceRef(f"ev_{document_id}_{block}", document_id, 1, page, (block,), Geometry(.1, .1, .3, .04), confidence, str(value))
    return ExtractedField(name, value, value if normalized is None else normalized, evidence, status)


@pytest.fixture
def consistent_fields():
    return [
        field("line_item_amount", "1000.00", 100000, block="line1"),
        field("line_item_amount", "500.00", 50000, block="line2"),
        field("invoice_total", "1500.00", 150000, block="total"),
        field("invoice_number", "INV-100", "INV-100", block="invoice"),
        field("provider_identifier", "HOSP-9", "HOSP-9", block="provider"),
        field("patient_identifier", "MEM-44", "MEM-44", block="patient_bill"),
        field("patient_identifier", "MEM-44", "MEM-44", document_id="doc_discharge", block="patient_summary"),
        field("admission_date", "2026-09-10", "2026-09-10", document_id="doc_discharge", block="admit"),
        field("discharge_date", "2026-09-12", "2026-09-12", document_id="doc_discharge", block="discharge"),
        field("procedure_date", "2026-09-11", "2026-09-11", document_id="doc_report", block="procedure"),
    ]
