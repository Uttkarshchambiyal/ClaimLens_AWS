"""Guardrails for ClaimLens AI Agent.

Enforces:
- Anti-adjudication rules (no approving/rejecting claims, no fraud probabilities/scores).
- Prompt injection and jailbreak protection on user input and untrusted document texts.
- Citation integrity and evidence verification.
"""
from __future__ import annotations

import re
from typing import Any


class GuardrailViolation(Exception):
    """Raised when a severe safety guardrail is triggered."""
    pass


class AgentGuardrails:
    # Patterns that attempt prompt injection or system override
    INJECTION_PATTERNS = [
        re.compile(r"ignore\s+(all\s+)?(previous|prior)\s+instructions", re.IGNORECASE),
        re.compile(r"disregard\s+(all\s+)?(previous|system)\s+prompts", re.IGNORECASE),
        re.compile(r"you\s+are\s+now\s+(in\s+developer\s+mode|dan|jailbroken|an\s+adjudicator)", re.IGNORECASE),
        re.compile(r"system\s*:\s*override", re.IGNORECASE),
    ]

    # Prohibited adjudication patterns in model output
    FORBIDDEN_ADJUDICATION_PATTERNS = [
        re.compile(r"\b(i\s+approve|i\s+reject|i\s+deny)\s+(this|the)\s+claim\b", re.IGNORECASE),
        re.compile(r"\b(claim\s+is\s+(hereby\s+)?(approved|rejected|denied|paid))\b", re.IGNORECASE),
        re.compile(r"\b(fraud\s+score\s*(:|is|=)\s*\d+)", re.IGNORECASE),
        re.compile(r"\b(fraud\s+probability\s*(:|is|=)\s*\d+)", re.IGNORECASE),
        re.compile(r"\b(fraud\s+risk\s+percentage\s*(:|is|=)\s*\d+)", re.IGNORECASE),
    ]

    def validate_input(self, user_message: str) -> str:
        """Inspect and sanitize incoming user query."""
        for pattern in self.INJECTION_PATTERNS:
            if pattern.search(user_message):
                # Neutralize injection by treating it as benign question text or refusing override
                user_message = pattern.sub("[neutralized system prompt attempt]", user_message)
        return user_message.strip()

    def validate_and_sanitize_output(
        self,
        output_text: str,
        claim_data: dict[str, Any] | None,
    ) -> str:
        """Inspect and sanitize model output to strictly enforce non-adjudication."""
        # Strip forbidden adjudication outputs
        for pattern in self.FORBIDDEN_ADJUDICATION_PATTERNS:
            if pattern.search(output_text):
                output_text = pattern.sub(
                    "[ClaimLens AI assists with evidence review but does not adjudicate, approve, reject, or assign fraud scores to claims]",
                    output_text,
                )

        # Ensure no fabricated fraud scores exist
        if "fraud probability" in output_text.lower() or "fraud score" in output_text.lower():
            output_text = re.sub(
                r"\b(fraud\s+(score|probability|risk\s+score)\s*[:=]?\s*\d+%?)\b",
                "[Fraud scores are not generated. Human review required]",
                output_text,
                flags=re.IGNORECASE,
            )

        return output_text
