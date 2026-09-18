from claimlens.config import Settings
from claimlens.models import CheckStatus
from claimlens.repository import InMemoryRepository
from claimlens.service import AnalysisService


def test_complete_local_upload_to_review_flow(consistent_fields):
    repo = InMemoryRepository(); service = AnalysisService(repo, Settings(use_bedrock=False))
    claim = service.create_claim("tenant-demo", "create-1")
    docs = []
    for i, kind in enumerate(("BILL", "DISCHARGE_SUMMARY", "SUPPORTING_REPORT")):
        docs.append(service.register_document("tenant-demo", claim["claimId"], f"synthetic-{i}.pdf", "application/pdf", kind, f"upload-{i}"))
    analysis = service.start_analysis("tenant-demo", claim["claimId"], [item["documentId"] for item in docs], "analysis-1")
    result = service.analyze_fields("tenant-demo", analysis["analysisId"], consistent_fields, {"BILL", "DISCHARGE_SUMMARY", "SUPPORTING_REPORT"}, semantic_error="BEDROCK_DISABLED")
    assert result["status"] == "COMPLETED_WITH_WARNINGS"
    assert result["reviewPriority"] == "MEDIUM"
    assert any(item["status"] == CheckStatus.ERROR.value for item in result["findings"])
    assert result["extractionQuality"] > 90
    assert result["coverage"] < 100


def test_partial_failure_never_becomes_clean(consistent_fields):
    repo = InMemoryRepository(); service = AnalysisService(repo, Settings())
    repo.put_once("tenant-demo", "ANALYSIS", "anl-1", {"claimId": "clm-1", "status": "PROCESSING", "analysisVersion": 1})
    result = service.analyze_fields("tenant-demo", "anl-1", consistent_fields, {"BILL"}, semantic_error="EXTRACTION_INCOMPLETE")
    assert result["status"] == "COMPLETED_WITH_WARNINGS"
    assert any(item["status"] in {"ERROR", "INSUFFICIENT_EVIDENCE"} for item in result["findings"])
