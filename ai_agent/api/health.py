"""Health API endpoint handler for ClaimLens AI Agent."""
from __future__ import annotations

import os
from typing import Any
from ai_agent.tools import ALL_TOOLS


def handle_health_request() -> dict[str, Any]:
    """Handle GET /api/ai/health requests."""
    provider = os.getenv("AI_MODEL_PROVIDER", "mock")
    return {
        "status": "HEALTHY",
        "service": "ClaimLens AI Assistant",
        "version": "0.1.0",
        "modelProvider": provider,
        "region": os.getenv("AWS_REGION", "ap-south-1"),
        "availableTools": [t.name for t in ALL_TOOLS],
        "guardrailsEnabled": True,
        "adjudicationDisabled": True,
    }
