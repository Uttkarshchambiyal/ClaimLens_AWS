#!/usr/bin/env python3
"""Structural checks for the generated synthetic OCR benchmark artifact."""
from __future__ import annotations

import json
from pathlib import Path

from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
PDF = ROOT / "output" / "pdf" / "claimlens-evaluation-benchmark.pdf"
GROUND_TRUTH = ROOT / "benchmarks" / "evaluation-ground-truth.json"


def main() -> int:
    truth = json.loads(GROUND_TRUTH.read_text())
    reader = PdfReader(str(PDF))
    if len(reader.pages) != 8 or len(truth.get("categories", [])) != 8:
        raise ValueError("Evaluation PDF and ground truth must contain eight benchmark categories")
    if len(truth.get("expectedFields", [])) < 30:
        raise ValueError("Evaluation ground truth is unexpectedly small")
    text = "\n".join((reader.pages[index].extract_text() or "") for index in (0, 1, 2, 4))
    for phrase in ("Synthetic Itemized Bill", "Repeated table header", "Tax and Adjustment Summary", "Procedure Terminology Variants"):
        if phrase not in text:
            raise ValueError(f"Benchmark page text is missing: {phrase}")
    if PDF.stat().st_size < 100_000:
        raise ValueError("Evaluation PDF is unexpectedly small")
    print(f"evaluation_artifact: PASS ({len(reader.pages)} pages, {len(truth['expectedFields'])} labeled fields)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
