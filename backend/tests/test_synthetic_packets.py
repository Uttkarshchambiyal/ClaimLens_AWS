import json
from pathlib import Path

import pytest

from claimlens.config import Settings
from claimlens.models import EvidenceRef, ExtractedField, Geometry
from claimlens.rules import run_deterministic_checks


SYNTHETIC = Path(__file__).parents[2] / "synthetic"


def load_packet(name):
    packet = json.loads((SYNTHETIC / name).read_text())
    fields = []
    for index, item in enumerate(packet["fields"]):
        ref = EvidenceRef(f"ev_{name}_{index}", item["documentId"], 1, 1, (item["blockId"],), Geometry(.1, .1, .4, .04), 97.0, item["value"])
        fields.append(ExtractedField(item["name"], item["value"], item.get("normalizedValue"), ref, item.get("normalizationStatus", "NORMALIZED")))
    return packet, fields


@pytest.mark.parametrize("name", ["consistent.json", "inconsistent.json", "ambiguous.json", "legitimate-edge.json"])
def test_synthetic_packet_expectations(name):
    packet, fields = load_packet(name)
    actual = {finding.check_id: finding.status.value for finding in run_deterministic_checks(fields, set(packet["documentTypes"]), Settings())}
    for check_id, expected in packet["expected"].items():
        assert actual[check_id] == expected
