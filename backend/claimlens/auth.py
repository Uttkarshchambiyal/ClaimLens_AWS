"""Cognito token customization for isolated self-service workspaces."""

from __future__ import annotations

import re
from typing import Any


TENANT_PATTERN = re.compile(r"[A-Za-z0-9_-]{1,80}")


def pre_token_generation_handler(event: dict[str, Any], _context: Any) -> dict[str, Any]:
    """Keep provisioned tenant IDs and derive one for self-registered users."""
    attributes = event.get("request", {}).get("userAttributes", {})
    tenant_id = attributes.get("custom:tenant_id") or attributes.get("sub") or event.get("userName")
    if not isinstance(tenant_id, str) or not TENANT_PATTERN.fullmatch(tenant_id):
        raise ValueError("Cognito user does not have a safe tenant identifier")
    event.setdefault("response", {})["claimsOverrideDetails"] = {
        "claimsToAddOrOverride": {"custom:tenant_id": tenant_id}
    }
    return event
