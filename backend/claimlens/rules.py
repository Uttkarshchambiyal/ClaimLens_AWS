from __future__ import annotations

from datetime import date
from decimal import Decimal
from hashlib import sha256
from typing import Iterable

from .config import Settings
from .models import CheckStatus, ExtractedField, Finding, Priority
from .money import format_inr


def _index(fields: Iterable[ExtractedField]) -> dict[str, list[ExtractedField]]:
    result: dict[str, list[ExtractedField]] = {}
    for item in fields:
        result.setdefault(item.name, []).append(item)
    return result


def _finding(check: str, title: str, summary: str, status: CheckStatus, priority: Priority, evidence: list[str], request: str | None = None) -> Finding:
    identity = sha256(f"{check}|{'|'.join(sorted(evidence))}|{status.value}".encode()).hexdigest()[:14]
    return Finding(f"f_{identity}", check, title, summary, status, priority, evidence, request)


def reconcile_bill(fields: Iterable[ExtractedField], settings: Settings) -> Finding:
    values = _index(fields)
    totals = values.get("invoice_total", [])
    lines = values.get("line_item_amount", [])
    adjustments = values.get("invoice_adjustment", [])
    reconciled_values = lines + adjustments + totals
    cited = [item.evidence.evidence_id for item in reconciled_values]
    if len({item.evidence.document_id for item in reconciled_values}) > 1:
        return _finding("bill.total_reconciliation", "Multiple bill sources need review", "Amounts from different invoices cannot be added into one reconciliation.", CheckStatus.INSUFFICIENT_EVIDENCE, Priority.MEDIUM, cited, "Review each invoice separately.")
    if not totals:
        return _finding("bill.total_reconciliation", "Invoice total unavailable", "The invoice total could not be extracted, so arithmetic reconciliation was not possible.", CheckStatus.INSUFFICIENT_EVIDENCE, Priority.MEDIUM, [item.evidence.evidence_id for item in lines], "Request a legible page containing the invoice total.")
    if not lines:
        return _finding("bill.total_reconciliation", "Line items unavailable", "No reliable line-item amounts were extracted, so the stated invoice total was not treated as verified.", CheckStatus.INSUFFICIENT_EVIDENCE, Priority.MEDIUM, [totals[0].evidence.evidence_id], "Request a legible itemized bill.")
    if any(item.normalization_status != "NORMALIZED" or isinstance(item.normalized_value, bool) or not isinstance(item.normalized_value, (int, Decimal)) or item.normalized_value != int(item.normalized_value) for item in reconciled_values):
        return _finding("bill.total_reconciliation", "Amount normalization is ambiguous", "At least one monetary value could not be normalized unambiguously. The total check was not marked clean.", CheckStatus.INSUFFICIENT_EVIDENCE, Priority.MEDIUM, cited, "Confirm the currency and decimal separators on the source bill.")
    if len({int(item.normalized_value) for item in totals}) > 1:
        return _finding("bill.total_reconciliation", "Conflicting invoice totals", "The bill contains more than one distinct invoice total. Confirm the intended total before reconciliation.", CheckStatus.INSUFFICIENT_EVIDENCE, Priority.MEDIUM, cited)
    line_sum = sum(int(item.normalized_value) for item in lines)
    adjustment_sum = sum(int(item.normalized_value) for item in adjustments)
    calculated_total = line_sum + adjustment_sum
    invoice_total = int(totals[0].normalized_value)
    difference = invoice_total - calculated_total
    adjustment_text = f" after {format_inr(adjustment_sum)} in explicit adjustments" if adjustments else ""
    if abs(difference) <= settings.money_tolerance_paise:
        return _finding("bill.total_reconciliation", "Invoice total reconciles", f"Line items total {format_inr(line_sum)}{adjustment_text}, matching the stated invoice total within the configured {format_inr(settings.money_tolerance_paise)} tolerance.", CheckStatus.PASS, Priority.LOW, cited)
    return _finding("bill.total_reconciliation", "Invoice total does not reconcile", f"Line items total {format_inr(line_sum)}{adjustment_text}, a difference of {format_inr(difference)} from the stated invoice total {format_inr(invoice_total)}. Tolerance: {format_inr(settings.money_tolerance_paise)}.", CheckStatus.FINDING, Priority.HIGH, cited)


def check_patient_identity(fields: Iterable[ExtractedField]) -> Finding:
    values = _index(fields).get("patient_identifier", [])
    cited = [item.evidence.evidence_id for item in values]
    if len({item.evidence.document_id for item in values}) < 2 or any(item.normalization_status != "NORMALIZED" or not item.normalized_value for item in values):
        return _finding("packet.patient_identity", "Patient identity cannot be compared", "Fewer than two documents contain a reliable patient identifier.", CheckStatus.INSUFFICIENT_EVIDENCE, Priority.MEDIUM, cited, "Request a legible document with the patient name and masked member identifier.")
    normalized = {str(item.normalized_value).casefold().strip() for item in values if item.normalization_status == "NORMALIZED"}
    if len(normalized) == 1 and len(normalized) == len({str(v.normalized_value).casefold().strip() for v in values}):
        return _finding("packet.patient_identity", "Patient identifiers align", "The extracted patient identifiers agree across the available documents.", CheckStatus.PASS, Priority.LOW, cited)
    return _finding("packet.patient_identity", "Patient identifiers differ", "The packet contains patient identifiers that do not normalize to the same value.", CheckStatus.FINDING, Priority.HIGH, cited)


def check_timeline(fields: Iterable[ExtractedField], settings: Settings) -> Finding:
    values = _index(fields)
    admissions = values.get("admission_date", [])
    discharges = values.get("discharge_date", [])
    procedures = values.get("procedure_date", [])
    all_dates = admissions + discharges + procedures
    cited = [item.evidence.evidence_id for item in all_dates]
    if not admissions or not discharges:
        return _finding("packet.timeline", "Stay timeline is incomplete", "Admission and discharge dates are both required for a complete timeline check.", CheckStatus.INSUFFICIENT_EVIDENCE, Priority.MEDIUM, cited, "Request a discharge summary showing admission and discharge dates.")
    if any(item.normalization_status != "NORMALIZED" for item in all_dates) or len({item.normalized_value for item in admissions}) != 1 or len({item.normalized_value for item in discharges}) != 1:
        return _finding("packet.timeline", "Dates need confirmation", "Ambiguous or conflicting dates prevent a reliable timeline check.", CheckStatus.INSUFFICIENT_EVIDENCE, Priority.MEDIUM, cited, "Confirm the stay dates on the original documents.")
    try:
        admission = date.fromisoformat(str(admissions[0].normalized_value))
        discharge = date.fromisoformat(str(discharges[0].normalized_value))
        procedure_dates = [date.fromisoformat(str(item.normalized_value)) for item in procedures]
    except ValueError:
        return _finding("packet.timeline", "Dates are ambiguous", "At least one date cannot be normalized safely, so timeline consistency was not inferred.", CheckStatus.INSUFFICIENT_EVIDENCE, Priority.MEDIUM, cited, "Confirm ambiguous dates in the packet.")
    if discharge < admission:
        return _finding("packet.timeline", "Discharge precedes admission", "The normalized discharge date is earlier than the admission date.", CheckStatus.FINDING, Priority.HIGH, cited)
    for procedure in procedure_dates:
        delta_before = (admission - procedure).days
        delta_after = (procedure - discharge).days
        if delta_before > settings.stay_day_allowance or delta_after > settings.stay_day_allowance:
            return _finding("packet.timeline", "Procedure falls outside the stay window", f"A procedure date falls outside the admission-to-discharge window plus the configured {settings.stay_day_allowance}-day allowance.", CheckStatus.FINDING, Priority.HIGH, cited)
    return _finding("packet.timeline", "Timeline is internally consistent", f"Available dates fall within the stay window and configured {settings.stay_day_allowance}-day allowance.", CheckStatus.PASS, Priority.LOW, cited)


def check_supporting_reports(fields: Iterable[ExtractedField], document_types: set[str]) -> Finding:
    fields = list(fields)
    charges = [item for item in fields if item.name == "procedure_or_device_charge"]
    cited = [item.evidence.evidence_id for item in charges]
    if not charges:
        if not any(item.name == "line_item_amount" for item in fields):
            return _finding("packet.supporting_evidence", "Charge details unavailable", "Line items were not reliably extracted, so supporting-document requirements cannot be determined.", CheckStatus.INSUFFICIENT_EVIDENCE, Priority.MEDIUM, [])
        return _finding("packet.supporting_evidence", "Supporting report check not applicable", "No procedure or device charge requiring a supporting report was identified.", CheckStatus.NOT_APPLICABLE, Priority.LOW, [])
    if "SUPPORTING_REPORT" not in document_types:
        return _finding("packet.supporting_evidence", "Supporting report is missing", "A procedure or device charge is present, but the corresponding report is not in this packet. This does not establish that the procedure did not occur.", CheckStatus.INSUFFICIENT_EVIDENCE, Priority.MEDIUM, cited, "Request the relevant procedure, diagnostic, implant, or pharmacy support record.")
    return _finding("packet.supporting_evidence", "Confirm the supporting report matches", "A report is present, but its presence alone does not demonstrate support for the specific billed charge. Review the cited charge against the report.", CheckStatus.INSUFFICIENT_EVIDENCE, Priority.MEDIUM, cited, "Confirm that the supporting report corresponds to this charge.")


def check_historical_invoice(fields: Iterable[ExtractedField], historical_fingerprints: set[str]) -> Finding:
    values = _index(fields)
    signature_fields = values.get("invoice_number", []) + values.get("provider_identifier", []) + values.get("invoice_total", [])
    cited = [item.evidence.evidence_id for item in signature_fields]
    if any(len(values.get(name, [])) != 1 for name in ("invoice_number", "provider_identifier", "invoice_total")) or any(item.normalization_status != "NORMALIZED" or item.normalized_value is None for item in signature_fields):
        return _finding("history.invoice_match", "Historical matching is incomplete", "A reliable invoice number, provider identifier, and invoice total are required for historical matching.", CheckStatus.INSUFFICIENT_EVIDENCE, Priority.MEDIUM, cited, "Confirm the invoice number, provider identifier, and invoice total.")
    fingerprint = invoice_fingerprint(fields)
    if fingerprint in historical_fingerprints:
        return _finding("history.invoice_match", "Possible historical invoice match", "The normalized invoice number, provider identifier, and total match a prior tenant-scoped invoice. A reviewer should inspect both versions.", CheckStatus.FINDING, Priority.HIGH, cited)
    return _finding("history.invoice_match", "No historical invoice match", "No prior tenant-scoped invoice has the same normalized invoice number, provider identifier, and total.", CheckStatus.PASS, Priority.LOW, cited)


def invoice_fingerprint(fields: Iterable[ExtractedField]) -> str | None:
    values = _index(fields)
    signature_fields = values.get("invoice_number", []) + values.get("provider_identifier", []) + values.get("invoice_total", [])
    if any(len(values.get(name, [])) != 1 for name in ("invoice_number", "provider_identifier", "invoice_total")) or any(item.normalization_status != "NORMALIZED" or item.normalized_value is None for item in signature_fields):
        return None
    canonical = "|".join(sorted(f"{item.name}:{item.normalized_value}" for item in signature_fields))
    return sha256(canonical.encode()).hexdigest()


def run_deterministic_checks(fields: list[ExtractedField], document_types: set[str], settings: Settings, historical_fingerprints: set[str] | None = None) -> list[Finding]:
    return [reconcile_bill(fields, settings), check_patient_identity(fields), check_timeline(fields, settings), check_supporting_reports(fields, document_types), check_historical_invoice(fields, historical_fingerprints or set())]
