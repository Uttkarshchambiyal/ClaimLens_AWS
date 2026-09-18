from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any
from math import isfinite


class CheckStatus(str, Enum):
    PASS = "PASS"
    FINDING = "FINDING"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    ERROR = "ERROR"


class Priority(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


@dataclass(frozen=True)
class Geometry:
    left: float
    top: float
    width: float
    height: float

    def __post_init__(self):
        values = (self.left, self.top, self.width, self.height)
        if any(not isfinite(v) or v < 0 or v > 1 for v in values) or self.left + self.width > 1.001 or self.top + self.height > 1.001:
            raise ValueError("Evidence geometry must use normalized page coordinates")


@dataclass(frozen=True)
class EvidenceRef:
    evidence_id: str
    document_id: str
    document_version: int
    page: int
    block_ids: tuple[str, ...]
    geometry: Geometry
    confidence: float
    excerpt: str

    def __post_init__(self):
        if not self.evidence_id or not self.document_id or self.document_version < 1 or self.page < 1 or not self.block_ids:
            raise ValueError("Evidence must identify a versioned source page and at least one block")
        if not 0 <= self.confidence <= 100:
            raise ValueError("Extraction confidence must be between 0 and 100")
        if not self.excerpt.strip():
            raise ValueError("Evidence excerpt cannot be empty")


@dataclass(frozen=True)
class ExtractedField:
    name: str
    value: Any
    normalized_value: Any
    evidence: EvidenceRef
    normalization_status: str = "NORMALIZED"


@dataclass
class Finding:
    finding_id: str
    check_id: str
    title: str
    summary: str
    status: CheckStatus
    priority: Priority
    evidence_ids: list[str] = field(default_factory=list)
    requested_evidence: str | None = None
    source: str = "DETERMINISTIC"

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["status"] = self.status.value
        value["priority"] = self.priority.value
        return value


def validate_finding_evidence(finding: Finding, evidence: dict[str, EvidenceRef]) -> None:
    if finding.status in (CheckStatus.PASS, CheckStatus.FINDING) and not finding.evidence_ids:
        raise ValueError(f"{finding.check_id} requires source evidence")
    missing = [evidence_id for evidence_id in finding.evidence_ids if evidence_id not in evidence]
    if missing:
        raise ValueError(f"Unsupported evidence citations: {', '.join(missing)}")


def evidence_to_dict(ref: EvidenceRef) -> dict[str, Any]:
    value = asdict(ref)
    value["block_ids"] = list(ref.block_ids)
    return value
