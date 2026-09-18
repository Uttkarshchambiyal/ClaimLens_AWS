from claimlens.config import Settings
from claimlens.models import CheckStatus
from claimlens.money import parse_money_to_paise
from claimlens.rules import check_supporting_reports, reconcile_bill, run_deterministic_checks

from conftest import field


def test_decimal_safe_money_normalization():
    assert parse_money_to_paise("₹1,234.56").paise == 123456
    assert parse_money_to_paise("0.10").paise + parse_money_to_paise("0.20").paise == 30


def test_ambiguous_comma_is_not_silently_normalized():
    result = parse_money_to_paise("12,50")
    assert result.status == "AMBIGUOUS"
    assert result.paise is None


def test_bill_total_reconciles(consistent_fields):
    result = reconcile_bill(consistent_fields, Settings())
    assert result.status == CheckStatus.PASS


def test_bill_mismatch_is_source_backed():
    fields = [field("line_item_amount", "100.00", 10000, block="line"), field("invoice_total", "125.00", 12500, block="total")]
    result = reconcile_bill(fields, Settings(money_tolerance_paise=100))
    assert result.status == CheckStatus.FINDING
    assert set(result.evidence_ids) == {"ev_doc_bill_line", "ev_doc_bill_total"}


def test_ambiguous_amount_never_passes():
    fields = [field("line_item_amount", "12,50", None, block="line", status="AMBIGUOUS"), field("invoice_total", "12.50", 1250, block="total")]
    assert reconcile_bill(fields, Settings()).status == CheckStatus.INSUFFICIENT_EVIDENCE


def test_missing_report_requests_evidence_without_denial():
    result = check_supporting_reports([field("procedure_or_device_charge", "5000", 500000, block="implant")], {"BILL"})
    assert result.status == CheckStatus.INSUFFICIENT_EVIDENCE
    assert result.requested_evidence
    assert "does not establish" in result.summary


def test_consistent_packet_checks(consistent_fields):
    results = run_deterministic_checks(consistent_fields, {"BILL", "DISCHARGE_SUMMARY", "SUPPORTING_REPORT"}, Settings())
    assert all(result.status in set(CheckStatus) for result in results)
    assert results[0].status == CheckStatus.PASS
    assert results[1].status == CheckStatus.PASS
    assert results[2].status == CheckStatus.PASS
