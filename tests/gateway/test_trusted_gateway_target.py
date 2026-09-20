"""Fail-closed gateway boundary for the blocked trusted-target story."""

from __future__ import annotations

import dataclasses
import inspect
import json

import pytest

from agent import conversation_loop
from agent.turn_context import build_turn_context
from agent.turn_facade import TurnFacadeMixin
from gateway import trusted_target_issuer
from gateway.config import Platform
from gateway.platforms.base import BasePlatformAdapter
from gateway.run import GatewayRunner
from gateway.run_turn import GatewayTurnMixin
from gateway.session import SessionContext, SessionSource
from gateway.turn_context import TurnContext
from hermes_cli.plugins_dispatch import PluginDispatchMixin


_FORBIDDEN_PRODUCTION_NAMES = {
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


def test_no_production_issuance_delivery_api_or_injection_seam_exists():
    assert _FORBIDDEN_PRODUCTION_NAMES.isdisjoint(vars(trusted_target_issuer))
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
        field.name for field in dataclasses.fields(TurnContext)
    }
    assert not hasattr(GatewayTurnMixin, "_consume_trusted_gateway_target")
    assert not hasattr(PluginDispatchMixin, "_invoke_hook_with_gateway_target")
    assert not hasattr(BasePlatformAdapter, "trusted_gateway_adapter_id")


@pytest.mark.parametrize(
    "source",
    [
        SessionSource(platform=Platform.LOCAL, chat_id="cli", user_id="local"),
        SessionSource(platform=Platform.TELEGRAM, chat_id="chat-1", user_id="user-1"),
        SessionSource.from_dict(
            SessionSource(
                platform=Platform.TELEGRAM,
                chat_id="chat-1",
                user_id="user-1",
                message_id="message-1",
            ).to_dict()
        ),
        SessionSource(
            platform=Platform.TELEGRAM,
            chat_id="chat-1",
            user_id="user-1",
            message_id="message-1",
        ),
    ],
    ids=["local-cli", "normal-gateway", "restored", "hand-built"],
)
def test_all_current_source_routes_serialize_no_trusted_target(source):
    context = SessionContext(
        source=source,
        connected_platforms=[source.platform],
        home_channels={},
        session_id="session-1",
    )
    serialized = json.dumps(context.to_dict(), sort_keys=True)
    assert "trusted_gateway" not in serialized
    assert "target_delivery" not in serialized


def test_gateway_turn_context_has_no_generic_target_payload():
    turn = TurnContext(
        source=SessionSource(platform=Platform.TELEGRAM, chat_id="chat-1", user_id="user-1"),
        session_id="session-1",
        session_key="routing-key",
        message="hello",
    )
    assert "trusted_gateway_target" not in dataclasses.asdict(turn)
    assert "trusted_gateway_target_delivery" not in dataclasses.asdict(turn)
