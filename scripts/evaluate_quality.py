#!/usr/bin/env python3
"""Measure deterministic rule quality on labeled synthetic packets.

This is a local regression benchmark, not an OCR benchmark. Live Textract and
Bedrock measurements are produced by scripts/evaluate_live_aws.py.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from claimlens.config import Settings
from claimlens.models import EvidenceRef, ExtractedField, Geometry
from claimlens.quality import status_metrics
from claimlens.rules import run_deterministic_checks


def load_fields(path: Path) -> tuple[dict, list[ExtractedField]]:
    packet = json.loads(path.read_text())
    fields = []
    for index, item in enumerate(packet["fields"]):
        evidence = EvidenceRef(
            f"ev_{path.stem}_{index}", item["documentId"], 1, int(item.get("page", 1)),
            (item["blockId"],), Geometry(.1, .1, .4, .04), float(item.get("confidence", 97)), str(item["value"]),
        )
        fields.append(ExtractedField(
            item["name"], item["value"], item.get("normalizedValue"), evidence,
            item.get("normalizationStatus", "NORMALIZED"),
        ))
    return packet, fields


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=ROOT / "synthetic")
    parser.add_argument("--output", type=Path, default=ROOT / "docs" / "quality-benchmark-results.json")
    args = parser.parse_args()
    cases = []
    all_expected: dict[str, str] = {}
    all_actual: dict[str, str] = {}
    for path in sorted(args.input.glob("*.json")):
        packet, fields = load_fields(path)
        findings = run_deterministic_checks(fields, set(packet["documentTypes"]), Settings())
        actual = {finding.check_id: finding.status.value for finding in findings}
        expected = packet["expected"]
        case_metrics = status_metrics(expected, actual)
        cases.append({"case": path.name, "description": packet.get("description", ""), "expected": expected, "actual": {key: actual.get(key, "MISSING") for key in expected}, "metrics": case_metrics})
        for check_id, status in expected.items():
            qualified = f"{path.name}:{check_id}"
            all_expected[qualified] = status
            all_actual[qualified] = actual.get(check_id, "MISSING")
    metrics = status_metrics(all_expected, all_actual)
    report = {
        "checkedAt": datetime.now(timezone.utc).isoformat(),
        "scope": "Labeled synthetic normalized-field regression only; not live OCR or Bedrock accuracy.",
        "metrics": metrics,
        "statusDistribution": dict(sorted(Counter(all_expected.values()).items())),
        "cases": cases,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps(metrics, indent=2))
    return 0 if metrics["statusAccuracy"] == 1 and metrics["falseCleanCount"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
