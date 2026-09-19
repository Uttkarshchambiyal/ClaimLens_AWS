from __future__ import annotations

import pytest

from claimlens.config import Settings
from claimlens.extraction import fields_from_adapter
from claimlens.models import CheckStatus
from claimlens.quality import field_metrics, status_metrics
from claimlens.repository import InMemoryRepository
from claimlens.rules import reconcile_bill
from claimlens.service import AnalysisService
from claimlens.workflow import _adapter_fields


def word(block_id, text, page=1, confidence=98):
    return {
        "Id": block_id,
        "BlockType": "WORD",
        "Text": text,
        "Page": page,
        "Confidence": confidence,
        "Geometry": {"BoundingBox": {"Left": .1, "Top": .1, "Width": .2, "Height": .03}},
    }


def table(page, prefix, rows):
    blocks = []
    cell_ids = []
    for row_number, values in enumerate(rows, 1):
        for column, value in enumerate(values, 1):
            cell_id = f"{prefix}-c{row_number}-{column}"
            word_id = cell_id + "-w"
            cell_ids.append(cell_id)
            blocks.extend([
                {"Id": cell_id, "BlockType": "CELL", "RowIndex": row_number, "ColumnIndex": column, "Page": page,
                 "Relationships": [{"Type": "CHILD", "Ids": [word_id]}]},
                word(word_id, value, page),
            ])
    return [{"Id": prefix, "BlockType": "TABLE", "Page": page, "Relationships": [{"Type": "CHILD", "Ids": cell_ids}]}] + blocks


def test_multilingual_form_labels_are_mapped_without_translating_values():
    blocks = [
        {"Id": "key", "BlockType": "KEY_VALUE_SET", "EntityTypes": ["KEY"], "Page": 1,
         "Relationships": [{"Type": "CHILD", "Ids": ["label"]}, {"Type": "VALUE", "Ids": ["value"]}]},
        word("label", "कुल राशि", 1),
        {"Id": "value", "BlockType": "KEY_VALUE_SET", "EntityTypes": ["VALUE"], "Page": 1,
         "Relationships": [{"Type": "CHILD", "Ids": ["amount"]}]},
        word("amount", "₹1,129.50", 1),
    ]
    assert _adapter_fields(blocks)[0]["name"] == "invoice_total"


def test_low_confidence_ocr_cannot_become_a_clean_value():
    adapter = [{"name": "invoice_total", "value": "1000.00", "page": 1, "blocks": [word("low", "1000.00", confidence=51)]}]
    fields, _ = fields_from_adapter("doc", 1, adapter, Settings(min_field_confidence=80))
    assert fields[0].normalized_value == 100000
    assert fields[0].normalization_status == "LOW_CONFIDENCE"


def test_repeated_headers_adjustments_and_abbreviated_procedure_reconcile():
    blocks = table(1, "p1", [["Description", "Amount"], ["TKR surgery", "1000.00"]])
    blocks += table(2, "p2", [
        ["Description", "Amount"],
        ["GST", "180.00"],
        ["Discount", "50.00"],
        ["Round off", "-0.50"],
        ["Grand total", "1129.50"],
    ])
    adapter = _adapter_fields(blocks)
    assert [item["value"] for item in adapter if item["name"] == "line_item_amount"] == ["1000.00"]
    assert [item["value"] for item in adapter if item["name"] == "invoice_adjustment"] == ["180.00", "-50.00", "-0.50"]
    assert any(item["name"] == "billed_procedure" for item in adapter)
    adapter.append({"name": "invoice_total", "value": "1129.50", "page": 2, "blocks": [word("total", "1129.50", 2)]})
    fields, _ = fields_from_adapter("bill", 1, adapter, Settings())
    assert reconcile_bill(fields, Settings()).status == CheckStatus.PASS


def test_quality_metrics_report_false_clean_and_field_precision_recall():
    statuses = status_metrics(
        {"one": "FINDING", "two": "PASS", "three": "INSUFFICIENT_EVIDENCE"},
        {"one": "PASS", "two": "FINDING", "three": "PASS"},
    )
    assert statuses["findingPrecision"] == 0
    assert statuses["findingRecall"] == 0
    assert statuses["falseCleanCount"] == 2
    fields = field_metrics(
        [{"name": "invoice_total", "page": 1, "normalizedValue": 10000}],
        [{"name": "invoice_total", "page": 1, "normalizedValue": 10000}, {"name": "tax", "page": 1, "normalizedValue": 1000}],
    )
    assert fields["precision"] == .5 and fields["recall"] == 1


def test_packet_limit_accepts_ten_documents_and_rejects_eleven():
    repo = InMemoryRepository()
    repo.put_once("tenant", "CLAIM", "claim", {})
    document_ids = []
    for index in range(11):
        document_id = f"doc-{index}"
        document_ids.append(document_id)
        repo.put_once("tenant", "DOCUMENT", document_id, {
            "claimId": "claim", "documentType": "BILL" if index == 0 else "SUPPORTING_REPORT",
            "version": 1, "objectKey": document_id,
        })
    service = AnalysisService(repo, Settings())
    assert service.start_analysis("tenant", "claim", document_ids[:10], "ten")["status"] == "QUEUED"
    with pytest.raises(ValueError, match="1 to 10"):
        service.start_analysis("tenant", "claim", document_ids, "eleven")
