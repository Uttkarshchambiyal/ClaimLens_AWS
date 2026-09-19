import pytest

from claimlens.auth import pre_token_generation_handler


def event(attributes, username="generated-user"):
    return {"userName": username, "request": {"userAttributes": attributes}, "response": {}}


def test_preserves_an_existing_tenant_assignment():
    result = pre_token_generation_handler(
        event({"sub": "user-123", "custom:tenant_id": "claims-team"}), None
    )
    assert result["response"]["claimsOverrideDetails"]["claimsToAddOrOverride"] == {
        "custom:tenant_id": "claims-team"
    }


def test_gives_self_registered_user_a_private_tenant():
    result = pre_token_generation_handler(event({"sub": "user-123"}), None)
    assert result["response"]["claimsOverrideDetails"]["claimsToAddOrOverride"] == {
        "custom:tenant_id": "user-123"
    }


def test_rejects_unsafe_identity_values():
    with pytest.raises(ValueError):
        pre_token_generation_handler(event({}, "../unsafe"), None)
