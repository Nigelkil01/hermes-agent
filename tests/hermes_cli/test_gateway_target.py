"""Public value-only contract for trusted gateway canary targets."""

from __future__ import annotations

import dataclasses
import importlib
import logging

import pytest

from gateway import trusted_target_issuer
from hermes_cli.gateway_target import TrustedGatewayCanaryTarget


_ISSUED = "2026-09-19T16:00:00Z"


def _target() -> TrustedGatewayCanaryTarget:
    return TrustedGatewayCanaryTarget(
        platform="telegram",
        adapter_id="telegram:9001",
        chat_id="chat-1",
        user_id="user-1",
        session_id="session-1",
        nonce="nonce-synthetic-1",
        issued_at_utc=_ISSUED,
    )


def test_gateway_target_module_is_an_inert_value_module():
    module = importlib.import_module("hermes_cli.gateway_target")

    assert module.__all__ == ["TrustedGatewayCanaryTarget"]
    for forbidden in (
        "GatewayCanaryTargetFactory",
        "GatewayTargetIssuer",
        "GatewayTargetValidator",
        "stage_validated_envelope",
        "register_target_gate_callback",
        "deliver_runtime_issued_target",
        "discard_runtime_issued_target",
        "claim_runtime_issued_delivery",
        "_ISSUE_RUNTIME_TARGET",
        "_register_runtime_target",
    ):
        assert not hasattr(module, forbidden)


def test_blocked_production_boundary_exposes_no_mint_or_delivery_api():
    forbidden = {
        "_VerifiedGatewayCanaryEnvelope",
        "_GatewayTargetBinding",
        "_TrustedGatewayTargetDelivery",
        "_GatewayTargetIssuer",
        "_DesignatedHookCapability",
        "_new_gateway_target_issuer",
        "_new_gateway_target_binding",
        "_consume_gateway_target",
        "_take_trusted_gateway_target",
        "_discard_trusted_gateway_target",
        "_private_hook_payload",
        "_invoke_pre_llm_call_with_trusted_gateway_target",
    }
    assert forbidden.isdisjoint(vars(trusted_target_issuer))


def test_value_object_has_exact_frozen_slot_backed_shape_and_redacted_repr(caplog):
    target = _target()

    assert [field.name for field in dataclasses.fields(target)] == [
        "platform", "adapter_id", "chat_id", "user_id", "session_id", "nonce", "issued_at_utc"
    ]
    assert not hasattr(target, "__dict__")
    with pytest.raises(dataclasses.FrozenInstanceError):
        target.chat_id = "other"

    rendered = repr(target)
    assert "redacted" in rendered.lower()
    for raw in dataclasses.astuple(target):
        assert raw not in rendered

    with caplog.at_level(logging.INFO):
        logging.getLogger(__name__).info("target=%r", target)
    assert "nonce-synthetic-1" not in caplog.text
    assert "chat-1" not in caplog.text


@pytest.mark.parametrize(
    "field,value",
    [
        ("platform", ""),
        ("adapter_id", " "),
        ("chat_id", " chat-1"),
        ("user_id", None),
        ("session_id", 7),
        ("nonce", "nonce\nvalue"),
    ],
)
def test_value_object_rejects_noncanonical_or_empty_string_fields(field, value):
    values = dataclasses.asdict(_target())
    values[field] = value
    with pytest.raises(ValueError, match="invalid trusted gateway canary target"):
        TrustedGatewayCanaryTarget(**values)


@pytest.mark.parametrize(
    "timestamp",
    [
        "2026-09-19T16:00:00+00:00",
        "2026-09-19T12:00:00-04:00",
        "2026-09-19T16:00:00.000000Z",
        "2026-09-19 16:00:00Z",
        "2026-09-19T16:00:00",
        "not-a-time",
    ],
)
def test_value_object_accepts_only_canonical_utc_timestamp(timestamp):
    values = dataclasses.asdict(_target())
    values["issued_at_utc"] = timestamp
    with pytest.raises(ValueError, match="invalid trusted gateway canary target"):
        TrustedGatewayCanaryTarget(**values)
