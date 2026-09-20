"""Local / Mock model provider for offline development, benchmarking, and unit testing."""
from __future__ import annotations

import re
from typing import Any


class MockModelProvider:
    """Intelligent semantic and rule-grounded mock model provider that returns direct, question-specific answers."""

    def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.1,
        max_tokens: int = 1024,
    ) -> str:
        prompt_lower = prompt.lower()

        # Extract user question from prompt template if present
        match = re.search(r"User Question:\s*(.+?)(?:\n\nAnswer|\Z)", prompt, re.DOTALL | re.IGNORECASE)
        user_question = match.group(1).strip() if match else prompt
        user_q = user_question.lower()

        # Check if context indicates no claim data loaded
        has_no_claim = "no claim context is currently loaded" in prompt_lower or "claim id: unknown" in prompt_lower

        # 1. General healthcare/billing terminology questions (can be answered without claim context)
        if any(q in user_q for q in [
            "what is an itemized",
            "what is a discharge summary",
            "what is a claim",
            "what does claimlens do",
            "what is coding discrepancy",
            "what is claimlens",
        ]):
            if "itemized" in user_q:
                return (
                    "An itemized medical bill is a detailed breakdown of all individual services, medications, procedures, room charges, and diagnostics provided to a patient during care, along with their respective rates and quantities."
                )
            if "discharge summary" in user_q:
                return (
                    "A discharge summary is a clinical document prepared by medical providers at the conclusion of a hospital stay detailing the primary diagnosis, clinical findings, treatments administered, patient response, and discharge instructions."
                )
            return (
                "ClaimLens is an evidence-first claim integrity review system. It compares itemized bills against clinical discharge summaries and supporting reports, providing traceable evidence for human reviewers without calculating fraud scores or making automated payment decisions."
            )

        # 2. Specific claim questions when NO claim data is loaded
        if has_no_claim:
            if any(q in user_q for q in [
                "discrepanc", "finding", "total", "bill", "patient", "surgery", "document",
                "diagnos", "procedure", "operation", "when", "cost", "cholecystectomy", "amount", "final amount"
            ]):
                return (
                    "I don't have enough evidence in the current claim data to answer that. "
                    "Please upload the relevant claim documents or open a claim with the required data."
                )

        # 3. Explicit Missing Information (e.g. allergy, blood group, pre-existing conditions not present)
        if any(term in user_q for term in [
            "allergy", "allergies", "blood group", "blood type", "insurance policy number",
            "pre-existing", "family history", "employer"
        ]):
            return "I don't have enough evidence in the current claim data to answer that."

        # 4. Explicit Summary Request (ONLY when explicitly asked for summary)
        if any(term in user_q for term in [
            "summarize the claim", "give me a summary", "summarize this claim", "what do you know about this claim"
        ]):
            return (
                "Here is the summary for this claim:\n\n"
                "• **Claim ID**: CLM-20481 (Priority: HIGH)\n"
                "• **Primary Procedure**: Laparoscopic Cholecystectomy performed on March 12 [Doc: CityCare_discharge_summary.pdf, Page: 1]\n"
                "• **Financials**: Stated total of ₹248,500.00 vs extracted line items sum of ₹241,500.00 [Doc: CityCare_itemized_bill.pdf, Page: 3]\n"
                "• **Primary Finding**: ₹7,000.00 unitemized discrepancy under review [Doc: CityCare_itemized_bill.pdf, Page: 3]\n"
                "• **Documents**: 3 verified documents (Itemized Bill, Discharge Summary, Supporting Report)."
            )

        # 5. Financial & Final Amount Queries (e.g. "WHAT IS THE FINAL AMOUNT", "What is the total charges?")
        if any(term in user_q for term in [
            "final amount", "total amount", "grand total", "amount due", "net amount",
            "invoice total", "bill total", "total charge", "how much is the total",
            "how much is the bill", "what is the bill", "claimed amount", "rupees", "paise"
        ]) or (
            ("how much" in user_q or "what is the amount" in user_q or "amount" in user_q)
            and not any(p in user_q for p in ["surgery", "cholecystectomy", "operation", "procedure"])
        ):
            return (
                "The itemized bill lists a **stated invoice total (final amount) of ₹248,500.00** [Doc: CityCare_itemized_bill.pdf, Page: 3].\n\n"
                "• **Line Items Sum**: ₹241,500.00 [Doc: CityCare_itemized_bill.pdf, Page: 3]\n"
                "• **Variance**: ₹7,000.00 unitemized difference currently flagged for human reviewer verification."
            )

        # 6. Specific Procedure Cost Question (e.g. "How much was the surgery?")
        has_cost_keyword = bool(re.search(r"\b(?:how much|cost|costs|charge|charges|price|fee|rate)\b", user_q))
        has_proc_keyword = bool(re.search(r"\b(?:surgery|cholecystectomy|operation|procedure)\b", user_q))
        if has_cost_keyword and has_proc_keyword:
            return (
                "The charge for the Laparoscopic Cholecystectomy package is **₹145,000.00** (CPT 47562) [Doc: CityCare_itemized_bill.pdf, Page: 1].\n\n"
                "• **OT & Anesthesia**: ₹38,000.00 [Doc: CityCare_itemized_bill.pdf, Page: 2]\n"
                "• **Room & Nursing**: ₹36,000.00 [Doc: CityCare_itemized_bill.pdf, Page: 2]\n"
                "• **Pharmacy & Consumables**: ₹22,500.00 [Doc: CityCare_itemized_bill.pdf, Page: 3]"
            )

        # 7. Follow-up Questions (e.g. "When was it performed?", "When was that done?")
        if any(q in user_q for q in [
            "when was it", "when was that", "what date", "performed on", "date of surgery", "date of procedure"
        ]):
            return (
                "The surgical procedure (Laparoscopic Cholecystectomy) was performed on **March 12** [Doc: CityCare_discharge_summary.pdf, Page: 1]."
            )

        # 8. Multi-Document Comparison Queries
        if any(term in user_q for term in [
            "compare", "both documents", "agree", "conflict", "versus", "vs", "reconcil",
            "discharge summary and the bill", "itemized bill and discharge", "across files",
            "appear in the discharge summary", "in the discharge summary"
        ]):
            return (
                "### Multi-Document Comparison Analysis\n\n"
                "• **Procedure / Clinical Consistency**:\n"
                "  - **Discharge Summary**: Confirms patient underwent *Laparoscopic Cholecystectomy* under general anesthesia [Doc: CityCare_discharge_summary.pdf, Page: 1].\n"
                "  - **Itemized Bill**: Lists *Laparoscopic Cholecystectomy Package (CPT 47562)* billed at ₹145,000.00 [Doc: CityCare_itemized_bill.pdf, Page: 1].\n"
                "  - **Clinical Alignment**: The clinical discharge narrative and itemized billing code align for the primary surgical procedure.\n\n"
                "• **Financial Reconciliation**:\n"
                "  - **Itemized Line Items Sum**: ₹241,500.00 [Doc: CityCare_itemized_bill.pdf, Page: 3].\n"
                "  - **Stated Invoice Total**: ₹248,500.00 [Doc: CityCare_itemized_bill.pdf, Page: 3].\n"
                "  - **Variance**: ₹7,000.00 unitemized discrepancy requiring reviewer verification."
            )


        # 9. Paraphrased Surgery / Procedure Questions (e.g. "What surgery did the patient have?", "What operation was done?")
        if any(term in user_q for term in [
            "what surgery", "which surgery", "what operation", "which operation",
            "what procedure", "which procedure", "cholecystectomy", "laparoscopic",
            "surgical treatment", "treatment did the patient receive", "what operation did the patient undergo",
            "procedure was performed", "surgery did the patient have"
        ]):
            if "when" in user_q or "date" in user_q or "time" in user_q:
                return (
                    "The patient underwent a **Laparoscopic Cholecystectomy** on **March 12** [Doc: CityCare_discharge_summary.pdf, Page: 1]. "
                    "The procedure was performed under general anesthesia with standard 4-port laparoscopic entry."
                )
            return (
                "The patient underwent a **Laparoscopic Cholecystectomy** (gallbladder removal) [Doc: CityCare_discharge_summary.pdf, Page: 1].\n\n"
                "• **Billed Code**: CPT 47562 — Laparoscopic Cholecystectomy [Doc: CityCare_itemized_bill.pdf, Page: 1]\n"
                "• **Billed Amount**: ₹145,000.00 [Doc: CityCare_itemized_bill.pdf, Page: 1]"
            )

        # 10. Discrepancies & Findings Questions
        if any(term in user_q for term in ["discrepanc", "findings", "issues", "flag", "checks", "mismatch", "why was this claim flagged"]):
            return (
                "Here are the findings identified in this claim packet:\n\n"
                "1. **Invoice total does not reconcile** [Finding]\n"
                "   • Stated Total: ₹248,500.00 vs Sum: ₹241,500.00 (₹7,000.00 difference)\n"
                "   • Source: [Doc: CityCare_itemized_bill.pdf, Page: 3]\n\n"
                "2. **Patient identifiers align** [Passed]\n"
                "   • Patient name and admission details match across itemized bill and discharge summary.\n"
                "   • Source: [Doc: CityCare_discharge_summary.pdf, Page: 1]\n\n"
                "3. **Supporting documentation present** [Passed]\n"
                "   • Lab and diagnostic records are present in the packet."
            )

        # 11. Documents & Extraction Quality
        if any(term in user_q for term in ["documents", "files", "packet", "uploaded", "pages", "quality"]):
            return (
                "The current claim packet contains the following documents:\n\n"
                "1. **CityCare_itemized_bill.pdf** (BILL) — 3 pages, extraction quality 94% [Doc: CityCare_itemized_bill.pdf, Page: 1]\n"
                "2. **CityCare_discharge_summary.pdf** (DISCHARGE_SUMMARY) — 2 pages, extraction quality 96% [Doc: CityCare_discharge_summary.pdf, Page: 1]\n"
                "3. **CityCare_lab_report.pdf** (SUPPORTING_REPORT) — 1 page, extraction quality 98% [Doc: CityCare_lab_report.pdf, Page: 1]"
            )

        # 12. Reviewer Actions & History
        if any(term in user_q for term in ["reviewer", "action", "disposition", "audit", "correction", "resolved", "acknowledged"]):
            return (
                "Reviewer activity and current disposition status:\n\n"
                "• **Invoice total discrepancy**: Acknowledged by reviewer.\n"
                "• **Patient identifiers**: Verified.\n"
                "• **Audit log**: Review disposition changes and annotations are preserved in the immutable audit trail."
            )

        # 13. Direct Answer Fallback (NO boilerplate overview)
        return (
            "Based on the claim documents, the primary procedure is Laparoscopic Cholecystectomy [Doc: CityCare_discharge_summary.pdf, Page: 1] "
            "with a stated total of ₹248,500.00 on [Doc: CityCare_itemized_bill.pdf, Page: 3]."
        )



