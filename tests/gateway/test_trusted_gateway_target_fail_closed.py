"""Regression coverage for the deliberately blocked trusted-target activation lane."""

from __future__ import annotations

import dataclasses
import inspect
from types import SimpleNamespace

import pytest

from agent import conversation_loop
from agent.turn_context import _collect_pre_llm_call_context, build_turn_context
from agent.turn_facade import TurnFacadeMixin
from gateway.run import GatewayRunner
from gateway.turn_context import TurnContext as GatewayTurnContext
import gateway.trusted_target_issuer as trusted_target_issuer
from hermes_cli import lifecycle, plugins
from hermes_cli.gateway_target import TrustedGatewayCanaryTarget
from hermes_cli.plugins import PluginManager
from hermes_cli.plugins_dispatch import PluginDispatchMixin


_FORBIDDEN_ISSUER_NAMES = {
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
    "_private_hook_should_skip",
    "_private_hook_payload",
    "_invoke_pre_llm_call_with_trusted_gateway_target",
}


def _target() -> TrustedGatewayCanaryTarget:
    return TrustedGatewayCanaryTarget(
        platform="telegram",
        adapter_id="bot:123",
        chat_id="456",
        user_id="789",
        session_id="session-1",
        nonce="nonce-1",
        issued_at_utc="2026-09-19T12:00:00Z",
    )


def test_no_production_issuance_delivery_api_or_injection_seam_exists():
    assert _FORBIDDEN_ISSUER_NAMES.isdisjoint(vars(trusted_target_issuer))
    assert "_gateway_target_verifier" not in inspect.signature(GatewayRunner).parameters
    assert "trusted_gateway_target_delivery" not in inspect.signature(
        TurnFacadeMixin.run_conversation
    ).parameters
    assert "trusted_gateway_target_delivery" not in inspect.signature(
        conversation_loop.run_conversation
    ).parameters
    assert "trusted_gateway_target_delivery" not in inspect.signature(
        build_turn_context
    ).parameters
    assert "trusted_gateway_target_delivery" not in {
        field.name for field in dataclasses.fields(GatewayTurnContext)
    }
    assert not hasattr(PluginDispatchMixin, "_invoke_hook_with_gateway_target")


def test_direct_value_cannot_enter_the_core_pre_llm_boundary():
    with pytest.raises(TypeError, match="trusted_gateway_target_delivery"):
        _collect_pre_llm_call_context(
            SimpleNamespace(
                _persist_disabled=False,
                session_id="session-1",
                model="test-model",
                platform="telegram",
                _parent_session_id=None,
                _user_id="user-1",
            ),
            effective_task_id="task-1",
            turn_id="turn-1",
            original_user_message="hello",
            messages=[{"role": "user", "content": "hello"}],
            conversation_history=[],
            trusted_gateway_target_delivery=_target(),
        )


@pytest.mark.parametrize(
    ("route", "platform", "history"),
    [
        ("local", "local", None),
        ("cli", "cli", []),
        ("normal-gateway", "telegram", []),
        ("restored", "telegram", [{"role": "user", "content": "prior"}]),
        ("hand-built", "", []),
    ],
)
def test_every_current_route_emits_no_trusted_target(
    monkeypatch, route, platform, history
):
    constructed_value = _target()
    seen = []

    def capture(hook_name, **payload):
        seen.append((hook_name, payload))
        return []

    monkeypatch.setattr(lifecycle, "invoke_hook", capture)
    agent = SimpleNamespace(
        _persist_disabled=False,
        session_id=f"session-{route}",
        model="test-model",
        platform=platform,
        _parent_session_id=None,
        _user_id="user-1",
    )

    assert _collect_pre_llm_call_context(
        agent,
        effective_task_id="task-1",
        turn_id="turn-1",
        original_user_message="hello",
        messages=[{"role": "user", "content": "hello"}],
        conversation_history=history,
    ) == ""
    assert repr(constructed_value) == "TrustedGatewayCanaryTarget(<redacted>)"
    assert len(seen) == 1
    hook_name, payload = seen[0]
    assert hook_name == "pre_llm_call"
    assert "trusted_gateway_target" not in payload
    assert constructed_value not in payload.values()


def test_generic_pre_llm_hook_preserves_payload_without_target_or_serialized_carrier(
    monkeypatch,
):
    monkeypatch.setattr(plugins, "_resolve_hook_callback_timeout", lambda: 0.0)
    manager = PluginManager()
    seen = []

    def callback(**payload):
        seen.append(payload)
        return {"context": "ordinary context"}

    manager._hooks["pre_llm_call"] = [callback]
    assert manager.invoke_hook("pre_llm_call", session_id="session-1") == [
        {"context": "ordinary context"}
    ]
    assert len(seen) == 1
    assert "trusted_gateway_target" not in seen[0]
    assert "trusted_gateway_target_delivery" not in dataclasses.asdict(
        GatewayTurnContext()
    )
