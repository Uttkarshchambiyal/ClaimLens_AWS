import pytest

from claimlens.config import Settings
from claimlens.repository import InMemoryRepository, TenantDenied
from claimlens.service import AnalysisService


class Orchestrator:
    def __init__(self): self.calls = []
    def start(self, analysis_id, payload): self.calls.append((analysis_id, payload))


def test_tenant_isolation_blocks_cross_tenant_claim_access():
    repo = InMemoryRepository()
    repo.put_once("tenant-a", "CLAIM", "clm-1", {"status": "DRAFT"})
    with pytest.raises(TenantDenied): repo.get_for_tenant("tenant-b", "CLAIM", "clm-1")


def test_duplicate_claim_request_returns_same_record():
    service = AnalysisService(InMemoryRepository(), Settings())
    first = service.create_claim("tenant-a", "same-key")
    second = service.create_claim("tenant-a", "same-key")
    assert first == second


def test_duplicate_analysis_starts_worker_once():
    repo = InMemoryRepository(); orchestrator = Orchestrator(); service = AnalysisService(repo, Settings(), orchestrator)
    repo.put_once("tenant-a", "CLAIM", "clm-1", {"status": "DRAFT"})
    repo.put_once("tenant-a", "DOCUMENT", "doc-1", {"claimId": "clm-1", "documentType": "BILL", "version": 1, "objectKey": "tenant-a/source.pdf"})
    first = service.start_analysis("tenant-a", "clm-1", ["doc-1"], "request-1")
    second = service.start_analysis("tenant-a", "clm-1", ["doc-1"], "request-1")
    assert first == second
    assert len(orchestrator.calls) == 1
