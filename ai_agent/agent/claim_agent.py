"""ClaimLens AI Agent orchestrator using Strands Agents SDK paradigm.

Coordinates tools, semantic hybrid retrieval, model providers, and guardrails to provide
evidence-grounded assistance to human claim reviewers.
"""
from __future__ import annotations

import json
import re
from typing import Any

from ai_agent.agent.guardrails import AgentGuardrails
from ai_agent.agent.prompts import CLAIMLENS_SYSTEM_PROMPT, USER_QUERY_PROMPT_TEMPLATE
from ai_agent.models import get_model_provider
from ai_agent.retrieval.context_builder import ContextBuilder
from ai_agent.retrieval.hybrid_retriever import HybridRetriever
from ai_agent.retrieval.source_validator import SourceValidator
from ai_agent.tools import ALL_TOOLS


class ClaimAgent:
    """Strands-compatible ClaimLens AI Agent with semantic hybrid retrieval, intent classification, and question-first answering."""

    def __init__(
        self,
        model_provider=None,
        tools: list | None = None,
        context_builder: ContextBuilder | None = None,
        hybrid_retriever: HybridRetriever | None = None,
        source_validator: SourceValidator | None = None,
        guardrails: AgentGuardrails | None = None,
    ):
        self.model_provider = model_provider or get_model_provider()
        self.tools = {tool.name: tool for tool in (tools or ALL_TOOLS)}
        self.context_builder = context_builder or ContextBuilder()
        self.hybrid_retriever = hybrid_retriever or HybridRetriever()
        self.source_validator = source_validator or SourceValidator()
        self.guardrails = guardrails or AgentGuardrails()

    def classify_intent(self, query: str) -> str:
        """Classify user query into a primary intent category."""
        q = query.lower()

        # Check explicit summary request
        if any(term in q for term in ["summarize the claim", "give me a summary", "summarize this claim", "what do you know about this claim", "claim summary"]):
            return "CLAIM_SUMMARY"

        # General terminology
        if any(q.startswith(term) or term in q for term in ["what is an itemized", "what is a discharge summary", "what does claimlens", "what is claimlens"]):
            return "GENERAL_TERMINOLOGY"

        # Comparison
        if any(term in q for term in ["compare", "both documents", "agree", "conflict", "versus", "vs", "reconcil", "across files"]):
            return "COMPARISON"

        # Financial & Amounts
        if any(term in q for term in ["final amount", "total amount", "grand total", "how much", "cost", "charges", "rupees", "paise", "bill total", "invoice total", "math", "amount due", "net amount"]):
            return "FINANCIAL"

        # Procedure & Clinical
        if any(term in q for term in ["surgery", "operation", "procedure", "cholecystectomy", "laparoscopic", "clinical", "diagnos", "treatment"]):
            return "PROCEDURE"

        # Findings & Discrepancies
        if any(term in q for term in ["discrepanc", "finding", "issue", "flag", "checks", "mismatch"]):
            return "DISCREPANCY"

        # Reviewer & Audit
        if any(term in q for term in ["reviewer", "action", "disposition", "audit", "correction"]):
            return "REVIEWER_AUDIT"

        # Document Roster
        if any(term in q for term in ["documents", "files", "packet", "uploaded", "pages"]):
            return "DOCUMENT_ROSTER"

        return "GENERAL_QUERY"

    def _resolve_conversational_query(
        self,
        user_message: str,
        conversation_history: list[dict[str, str]] | None,
    ) -> str:
        """Enrich user query with antecedent context from conversational history for semantic retrieval."""
        if not conversation_history:
            return user_message

        follow_up_cues = [
            r"\bit\b", r"\bthat\b", r"\bthis\b", r"\bthem\b", r"\bthey\b",
            r"\bthe procedure\b", r"\bthe surgery\b", r"\bthe operation\b",
            r"\bthe bill\b", r"\bthe total\b", r"\bthe doctor\b", r"\bthe hospital\b",
            r"\bwhen was it\b", r"\bhow much of that\b", r"\bwhere was it\b", r"\bwhy\b",
        ]
        is_follow_up = any(re.search(cue, user_message, re.IGNORECASE) for cue in follow_up_cues)

        if not is_follow_up:
            return user_message

        recent_turns = conversation_history[-3:]
        prior_contexts = []
        for turn in recent_turns:
            content = turn.get("content") or turn.get("text") or ""
            entities = re.findall(r"\b[A-Za-z]{4,}\b", content)
            filtered = [
                w for w in entities
                if w.lower() not in {
                    "what", "when", "where", "which", "there", "their", "about",
                    "would", "could", "should", "please", "claim", "lens", "assistant"
                }
            ]
            if filtered:
                prior_contexts.extend(filtered[:6])

        if prior_contexts:
            return f"{user_message} (context: {' '.join(prior_contexts[:8])})"

        return user_message

    def _validate_and_clean_answer_relevance(self, answer: str, intent: str) -> str:
        """Strip unsolicited generic claim summaries or trailing prompt suggestions unless requested."""
        cleaned = answer

        # Strip generic "Ask me about..." footers
        cleaned = re.sub(
            r"\n*(?:Ask me about|Feel free to ask about|How else can I assist with this claim review\??).*$",
            "",
            cleaned,
            flags=re.IGNORECASE | re.DOTALL,
        ).strip()

        # If user did NOT ask for a claim summary, remove generic preamble like "I am reviewing claim CLM-..."
        if intent != "CLAIM_SUMMARY":
            cleaned = re.sub(
                r"^I am reviewing claim [A-Za-z0-9_-]+ with \d+ document\(s\) and \d+ findings?\.\s*",
                "",
                cleaned,
                flags=re.IGNORECASE,
            ).strip()
            cleaned = re.sub(
                r"^I have analyzed the current claim\.\s*The packet includes [^.]+\.\s*",
                "",
                cleaned,
                flags=re.IGNORECASE,
            ).strip()

        return cleaned

    def process_query(
        self,
        user_message: str,
        claim_data: dict[str, Any] | None = None,
        conversation_history: list[dict[str, str]] | None = None,
    ) -> dict[str, Any]:
        """Process user message and return grounded response with verified citations."""
        # 1. Input Guardrail
        sanitized_input = self.guardrails.validate_input(user_message)

        # 2. Intent Classification
        intent = self.classify_intent(sanitized_input)

        # 3. Build Claim Context
        claim_context_str = self.context_builder.build_claim_context(claim_data)

        # 4. Contextualize query for semantic search
        retrieval_query = self._resolve_conversational_query(sanitized_input, conversation_history)

        # 5. Hybrid Semantic & Lexical Retrieval
        relevant_evidence = self.hybrid_retriever.retrieve(
            query=retrieval_query,
            claim_data=claim_data,
            top_k=5,
        )

        # For financial questions, prioritize bill chunks over discharge summary chunks
        if intent == "FINANCIAL" and relevant_evidence:
            relevant_evidence = sorted(
                relevant_evidence,
                key=lambda x: (0 if x.get("documentType") == "BILL" or "bill" in (x.get("documentName") or "").lower() else 1),
            )

        evidence_str = (
            json.dumps(relevant_evidence, indent=2)
            if relevant_evidence
            else "No specific evidence fragments matched."
        )

        # 6. Format Conversation History for Prompt
        history_str = ""
        if conversation_history:
            history_lines = ["Conversation History:"]
            for turn in conversation_history[-4:]:
                role = turn.get("role", "User").capitalize()
                text = turn.get("content") or turn.get("text", "")
                history_lines.append(f"{role}: {text}")
            history_lines.append("")
            history_str = "\n".join(history_lines) + "\n"

        # 7. Construct Prompt
        full_user_prompt = USER_QUERY_PROMPT_TEMPLATE.format(
            claim_context=claim_context_str,
            relevant_evidence=evidence_str,
            conversation_history=history_str,
            user_message=sanitized_input,
        )

        # 8. Generate Model Response
        raw_response = self.model_provider.generate(
            prompt=full_user_prompt,
            system_prompt=CLAIMLENS_SYSTEM_PROMPT,
        )

        # 9. Extract and Validate Citations
        cleaned_text, parsed_citations = self.source_validator.extract_and_validate_citations_from_text(
            raw_response, claim_data
        )

        # 10. Question Relevance & Boilerplate Cleanup
        cleaned_text = self._validate_and_clean_answer_relevance(cleaned_text, intent)

        # 11. Combine parsed citations with top retrieved evidence if not explicitly in text
        final_sources = list(parsed_citations)
        if not final_sources and relevant_evidence:
            for ev in relevant_evidence[:2]:
                doc_name = ev.get("documentName", "")
                page = ev.get("page", 1)
                if not any(s.get("documentName") == doc_name and s.get("page") == page for s in final_sources):
                    final_sources.append({
                        "evidenceId": ev.get("chunkId") or ev.get("evidenceId"),
                        "documentName": doc_name,
                        "page": page,
                        "confidence": ev.get("confidence", 100.0),
                        "excerpt": ev.get("excerpt", ""),
                    })

        # 12. Output Guardrail (Enforce non-adjudication, strip forbidden statements)
        final_answer = self.guardrails.validate_and_sanitize_output(cleaned_text, claim_data)

        return {
            "answer": final_answer,
            "sources": final_sources,
            "confidence": 0.95 if (claim_data and final_sources) else None,
            "status": "COMPLETED",
        }


