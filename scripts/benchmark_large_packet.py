#!/usr/bin/env python3
"""Exercise the maximum supported local packet and record payload/time bounds."""
from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from claimlens.config import Settings
from claimlens.models import EvidenceRef, ExtractedField, Geometry
from claimlens.repository import InMemoryRepository
from claimlens.service import AnalysisService


def field(index: int, name: str, value, document_id: str) -> ExtractedField:
    ref = EvidenceRef(
        f"ev_large_{index}", document_id, 1, index // 20 + 1, (f"b{index}",),
        Geometry(.05, .05 + (index % 20) * .04, .4, .025), 96.0, str(value),
    )
    return ExtractedField(name, str(value), value, ref, "NORMALIZED")


def main() -> int:
    fields = [
        field(0, "line_item_amount", 100000, "bill"),
        field(1, "invoice_total", 100000, "bill"),
        field(2, "invoice_number", "INV-LARGE-1", "bill"),
        field(3, "provider_identifier", "HOSP-LARGE", "bill"),
        field(4, "patient_identifier", "MEM-LARGE", "bill"),
    ]
    for index in range(5, 120):
        document_id = f"support-{(index - 5) % 9}"
        fields.append(field(index, "clinical_statement", f"Synthetic source-cited statement {index}", document_id))
    payload_bytes = len(json.dumps([asdict(item) for item in fields], default=str).encode())
    repo = InMemoryRepository()
    repo.put_once("benchmark", "ANALYSIS", "large", {"claimId": "large", "status": "PROCESSING", "analysisVersion": 1})
    started = time.perf_counter()
    result = AnalysisService(repo, Settings()).analyze_fields("benchmark", "large", fields, {"BILL", "SUPPORTING_REPORT"})
    elapsed_ms = round((time.perf_counter() - started) * 1000, 3)
    report = {
        "checkedAt": datetime.now(timezone.utc).isoformat(),
        "scope": "Local maximum-shape benchmark only; does not measure AWS service latency or quotas.",
        "documents": 10,
        "fields": len(fields),
        "serializedFieldBytes": payload_bytes,
        "configuredFieldLimit": 120,
        "configuredCombinedByteLimit": 220000,
        "elapsedMs": elapsed_ms,
        "analysisStatus": result["status"],
        "withinBounds": len(fields) <= 120 and payload_bytes <= 220000,
    }
    output = ROOT / "docs" / "large-packet-benchmark.json"
    output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    return 0 if report["withinBounds"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
