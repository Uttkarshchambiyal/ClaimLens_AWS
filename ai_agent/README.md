# ClaimLens AI Review Assistant (`ai_agent`)

The **ClaimLens AI Assistant** is an intelligent pair-review agent for medical claims examiners. It integrates with the existing ClaimLens platform to provide context-aware, evidence-grounded answers, explain discrepancy findings, inspect line items, and navigate source document pages.

ClaimLens remains the **single source of truth**; the AI agent is an intelligence layer that reads claim data, retrieves evidence, and assists human decision-makers without ever deciding payment or calculating fraud probabilities.

---

## 1. Architecture

```text
                     ClaimLens Reviewer Workspace
                                │
                    ┌───────────┴───────────┐
                    ▼                       ▼
            Existing UI Views         AI Assistant Chat
          (Queue / Findings / Docs)  (AgentChat / Evidence)
                    │                       │
                    └───────────┬───────────┘
                                │
                                ▼
                       ClaimLens Backend & API
                   (POST /api/ai/chat, upload, health)
                                │
                                ▼
                        Strands ClaimAgent
                                │
                    ┌───────────┴───────────┐
                    │                       │
             Retrieval & Tools         Guardrails &
            (Context, Evidence)      Source Validator
                    │                       │
                    └───────────┬───────────┘
                                │
                                ▼
                    Model Provider Interface
                    ├── Local: MockModelProvider
                    └── Prod:  SageMakerModelProvider
```

---

## 2. Key Components

* **`agent/claim_agent.py`**: Coordinates tool calling, evidence retrieval, context compilation, guardrails, and model execution using the **Strands Agents SDK** paradigm.
* **`agent/prompts.py`**: System instructions, few-shot examples, and templates refined from **PartyRock** experimentation.
* **`agent/guardrails.py`**: Strict input/output safety filters that neutralize prompt injections and intercept forbidden adjudication outputs (e.g., automated approvals/denials or fraud scores).
* **`models/sagemaker.py`**: Production model provider that invokes an **Amazon SageMaker AI** endpoint via `sagemaker-runtime`.
* **`models/mock.py`**: Grounded, deterministic local model provider for offline development and testing.
* **`tools/`**: Clean tools for retrieving claim metadata, documents, evidence excerpts, discrepancy findings, financial breakdowns, reviewer dispositions, and audit events.
* **`retrieval/`**: Context builder with token budgeting, query-based evidence matcher, and a source validator that verifies every citation against actual claim documents.
* **`sessions/session_manager.py`**: Scoped conversation memory enforcing strict claim and tenant isolation.
* **`api/`**: REST/HTTP handlers for chat, file uploads, and health checks.

---

## 3. PartyRock Prototyping Workflow

PartyRock is used as an agile **prototyping and experimentation sandbox** for designing and testing:
1. System prompt instructions and few-shot formatting.
2. Evidence citation conventions (`[Doc: <name>, Page: <number>]`).
3. Conflict resolution logic when documents disagree.
4. Response structuring for missing evidence and general medical billing queries.

Once validated on PartyRock, refined prompt templates and behavioral guardrails are formalized in `ai_agent/agent/prompts.py` and executed in production via **Strands Agents SDK + SageMaker AI**. PartyRock is never a runtime dependency of the deployed stack.

---

## 4. Local Development vs. Production Configuration

### Local / Mock Mode (Default)
Run completely offline without AWS credentials:
```bash
# In ai_agent/.env or shell:
export AI_MODEL_PROVIDER=mock
```

### Production Mode (AWS SageMaker AI)
Deploy against an active SageMaker inference endpoint:
```bash
export AI_MODEL_PROVIDER=sagemaker
export AWS_REGION=ap-south-1
export SAGEMAKER_ENDPOINT_NAME=claimlens-assistant-endpoint
export SAGEMAKER_MODEL_NAME=meta-llama-3-8b-instruct
```

---

## 5. API Endpoints

### 1. `POST /api/ai/chat`
Send a question to the assistant in the context of the active claim or session.

**Request:**
```json
{
  "session_id": "sess_optional_uuid",
  "claim_id": "CLM-20481",
  "message": "What is the discrepancy in the invoice total?"
}
```

**Response:**
```json
{
  "answer": "There is a ₹7,000.00 variance between the stated invoice total (₹248,500.00) and line item sum (₹241,500.00) on [Doc: CityCare_itemized_bill.pdf, Page: 3].",
  "sources": [
    {
      "evidenceId": "ev_01",
      "documentName": "CityCare_itemized_bill.pdf",
      "page": 3,
      "confidence": 98.4,
      "excerpt": "Invoice Total ₹248,500.00"
    }
  ],
  "confidence": 0.95,
  "session_id": "sess_optional_uuid"
}
```

### 2. `POST /api/ai/upload`
Upload a document into a temporary review session or attach to an existing claim.

### 3. `GET /api/ai/health`
Check service health, active model provider, and available tools.

---

## 6. Security and Adjudication Boundaries

* **No Automated Adjudication**: The agent never approves, denies, or pays claims.
* **No Fraud Scoring**: The agent never assigns fraud probabilities or risk scores.
* **Strict Tenant & Claim Isolation**: Conversations and evidence lookups are strictly partitioned by tenant ID and claim ID.
* **Untrusted Document Protection**: Text inside uploaded documents is treated as untrusted data and cannot override system instructions.

---

## 7. Running Tests

Run the complete test suite:
```bash
python3 -m pytest ai_agent/tests -v
```
