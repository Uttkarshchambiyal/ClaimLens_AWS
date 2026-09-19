from __future__ import annotations

from collections import Counter
import json
from typing import Any, Iterable


def _ratio(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 4) if denominator else 0.0


def status_metrics(expected: dict[str, str], actual: dict[str, str]) -> dict[str, Any]:
    """Measure exact status quality and finding detection without hiding missing output."""
    keys = sorted(expected)
    pairs = [(expected[key], actual.get(key, "MISSING")) for key in keys]
    true_positive = sum(want == "FINDING" and got == "FINDING" for want, got in pairs)
    false_positive = sum(want != "FINDING" and got == "FINDING" for want, got in pairs)
    false_negative = sum(want == "FINDING" and got != "FINDING" for want, got in pairs)
    precision = _ratio(true_positive, true_positive + false_positive)
    recall = _ratio(true_positive, true_positive + false_negative)
    false_clean = sum(want in {"FINDING", "INSUFFICIENT_EVIDENCE", "ERROR"} and got == "PASS" for want, got in pairs)
    confusion = Counter(f"{want}->{got}" for want, got in pairs)
    return {
        "evaluatedChecks": len(pairs),
        "exactMatches": sum(want == got for want, got in pairs),
        "statusAccuracy": _ratio(sum(want == got for want, got in pairs), len(pairs)),
        "findingPrecision": precision,
        "findingRecall": recall,
        "findingF1": _ratio(2 * precision * recall, precision + recall),
        "falseCleanCount": false_clean,
        "confusion": dict(sorted(confusion.items())),
    }


def _field_key(item: dict[str, Any]) -> tuple[str, int, str]:
    value = item.get("normalizedValue")
    return str(item.get("name", "")), int(item.get("page", 1)), json.dumps(value, sort_keys=True, ensure_ascii=False)


def field_metrics(expected: Iterable[dict[str, Any]], actual: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Multiset precision/recall for page-grounded normalized field extraction."""
    wanted = Counter(_field_key(item) for item in expected)
    observed = Counter(_field_key(item) for item in actual)
    true_positive = sum((wanted & observed).values())
    false_positive = sum((observed - wanted).values())
    false_negative = sum((wanted - observed).values())
    precision = _ratio(true_positive, true_positive + false_positive)
    recall = _ratio(true_positive, true_positive + false_negative)
    return {
        "expectedFields": sum(wanted.values()),
        "observedFields": sum(observed.values()),
        "truePositive": true_positive,
        "falsePositive": false_positive,
        "falseNegative": false_negative,
        "precision": precision,
        "recall": recall,
        "f1": _ratio(2 * precision * recall, precision + recall),
    }
