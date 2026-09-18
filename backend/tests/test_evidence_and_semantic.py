import pytest

from claimlens.semantic import validate_model_output

from conftest import field


def test_model_output_accepts_only_known_evidence():
    source = field("procedure_date", "2026-09-11", "2026-09-11")
    payload = {"findings": [{"checkId": "semantic.timeline", "title": "Aligned", "summary": "The supplied dates align.", "status": "PASS", "priority": "LOW", "evidenceIds": [source.evidence.evidence_id]}]}
    result = validate_model_output(payload, {source.evidence.evidence_id: source.evidence})
    assert result[0].source == "BEDROCK"


def test_model_output_rejects_unsupported_citation():
    payload = {"findings": [{"checkId": "semantic.timeline", "title": "Mismatch", "summary": "Dates differ.", "status": "FINDING", "priority": "HIGH", "evidenceIds": ["invented"]}]}
    with pytest.raises(ValueError, match="Unsupported evidence"):
        validate_model_output(payload, {})


def test_model_output_rejects_extra_keys_and_adjudication():
    source = field("procedure_date", "2026-09-11", "2026-09-11")
    invalid = {"findings": [{"checkId": "x", "title": "x", "summary": "Approve claim", "status": "PASS", "priority": "LOW", "evidenceIds": [source.evidence.evidence_id], "confidence": .9}]}
    with pytest.raises(ValueError, match="strict schema"):
        validate_model_output(invalid, {source.evidence.evidence_id: source.evidence})
