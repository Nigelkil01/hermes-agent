"""Fail-closed pre-LLM hook regressions for the blocked trusted-target story."""

from __future__ import annotations

import json
from contextlib import nullcontext
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from agent.turn_context import _collect_pre_llm_call_context, build_api_messages
from gateway.config import Platform
from gateway.run_turn_runner import TurnRunner
from gateway.turn_context import TurnContext
from hermes_cli.plugins import PluginContext, PluginManager
from hermes_cli.plugins_manifest import PluginManifest


def _agent(*, persist_disabled: bool = False, platform: str = "telegram"):
    return SimpleNamespace(
        _parent_session_id=None,
        _persist_disabled=persist_disabled,
        model="test/model",
        platform=platform,
        session_id="session-1",
        _user_id="user-1",
    )


def _collect(agent, user_message, messages, *, history=None):
    return _collect_pre_llm_call_context(
        agent,
        effective_task_id="task-1",
        turn_id="turn-1",
        original_user_message=user_message,
        messages=messages,
        conversation_history=history,
    )


def _plugin_manager(first_calls, second_calls):
    manager = PluginManager(scope_key="/tmp/jev-target-test")
    manager._discovered = True
    first = PluginContext(
        PluginManifest(name="hermes-token-router", key="hermes-token-router"), manager
    )
    second = PluginContext(
        PluginManifest(name="ordinary-plugin", key="ordinary-plugin"), manager
    )

    def first_hook(**kwargs):
        first_calls.append(kwargs)
        return {"context": "first-context"}

    def second_hook(**kwargs):
        second_calls.append(kwargs)
        return {"context": "second-context"}

    first.register_hook("pre_llm_call", first_hook)
    second.register_hook("pre_llm_call", second_hook)
    return manager


def test_generic_hooks_precede_provider_assembly_without_target_or_message_mutation(monkeypatch):
    first_calls, second_calls, order = [], [], []
    manager = _plugin_manager(first_calls, second_calls)
    messages = [{"role": "user", "content": "hello"}]
    before = json.dumps(messages, sort_keys=True)

    monkeypatch.setattr("hermes_cli.plugins._delivery_manager", lambda: manager)
    monkeypatch.setattr("hermes_cli.lifecycle._observe", lambda *_args, **_kwargs: None)
    context = _collect(_agent(), "hello", messages)
    order.append("hooks")

    from agent import replay_cleanup

    monkeypatch.setattr(
        replay_cleanup,
        "canonicalize_replay_history",
        lambda history, **kwargs: order.append("provider_assembly") or history,
    )
    assembly_agent = SimpleNamespace(
        _current_turn_timestamp=0.0,
        _copy_reasoning_content_for_api=lambda source, destination: None,
        _should_sanitize_tool_calls=lambda: False,
        ephemeral_system_prompt="",
    )
    api_messages, _ = build_api_messages(
        assembly_agent,
        messages,
        current_turn_user_idx=0,
        ext_prefetch_cache="",
        plugin_user_context=context,
        moa_config=None,
        active_system_prompt="",
    )

    assert order == ["hooks", "provider_assembly"]
    assert context == "first-context\n\nsecond-context"
    assert len(first_calls) == len(second_calls) == 1
    assert all("trusted_gateway_target" not in call for call in (*first_calls, *second_calls))
    assert json.dumps(messages, sort_keys=True) == before
    assert "trusted_gateway" not in json.dumps(api_messages, sort_keys=True)


def test_lifecycle_shell_webhook_and_serialized_payloads_stay_target_free(monkeypatch):
    from agent import outbound_webhooks, shell_hooks

    first_calls, second_calls, observer_calls = [], [], []
    manager = _plugin_manager(first_calls, second_calls)
    monkeypatch.setattr("hermes_cli.plugins._delivery_manager", lambda: manager)
    monkeypatch.setattr(
        "hermes_cli.lifecycle._observe",
        lambda name, **kwargs: observer_calls.append(kwargs),
    )

    _collect(_agent(), "hello", [{"role": "user", "content": "hello"}])

    assert len(first_calls) == len(second_calls) == len(observer_calls) == 1
    serialized = "\n".join(
        [
            shell_hooks._serialize_payload("pre_llm_call", second_calls[0]),
            outbound_webhooks._serialize_payload(
                "pre_llm_call", second_calls[0], "delivery-fail-closed"
            ).decode("utf-8"),
            json.dumps(observer_calls[0], sort_keys=True),
        ]
    )
    assert "trusted_gateway_target" not in serialized
    assert "TrustedGatewayCanaryTarget" not in serialized


def test_persistence_disabled_fork_invokes_no_hook(monkeypatch):
    first_calls, second_calls = [], []
    manager = _plugin_manager(first_calls, second_calls)
    monkeypatch.setattr("hermes_cli.plugins._delivery_manager", lambda: manager)
    observer = MagicMock()
    monkeypatch.setattr("hermes_cli.lifecycle._observe", observer)

    assert _collect(_agent(persist_disabled=True), "hello", []) == ""
    assert first_calls == second_calls == []
    observer.assert_not_called()


def test_turn_runner_passes_no_target_payload_or_result_field():
    source = SimpleNamespace(
        platform=Platform.TELEGRAM,
        chat_id="chat-1",
        user_id="user-1",
        user_name="Synthetic User",
        is_bot=False,
    )
    ctx = TurnContext(
        source=source,
        session_id="session-1",
        session_key="routing-key",
        message="hello",
    )
    runner = SimpleNamespace(_consume_pending_native_image_paths=lambda _key: [])
    captured = {}

    class _Agent:
        def run_conversation(self, message, **kwargs):
            captured["message"] = message
            captured["kwargs"] = kwargs
            return {"final_response": "ok", "messages": [{"role": "user", "content": message}]}

    turn_runner = TurnRunner(runner, ctx)
    with (
        patch("gateway.run._wrap_current_message_with_observed_context", side_effect=lambda message, _context: message),
        patch("tools.approval.register_gateway_notify"),
        patch("tools.approval.unregister_gateway_notify"),
        patch("tools.approval_context.set_current_session_key", return_value=object()),
        patch("tools.approval_context.reset_current_session_key"),
        patch("agent.notification_presentation.notification_turn", side_effect=lambda *a, **k: nullcontext()),
    ):
        result = turn_runner._run_conversation_with_approval(_Agent(), [], None, None, None)

    assert captured["message"] == "hello"
    assert "trusted_gateway_target" not in captured["kwargs"]
    assert "trusted_gateway_target_delivery" not in captured["kwargs"]
    assert "trusted_gateway" not in str(result)


def test_legacy_agent_callers_remain_compatible():
    source = SimpleNamespace(platform=Platform.LOCAL, chat_id="cli", user_id="local")
    ctx = TurnContext(source=source, session_id="session-1", session_key="routing-key", message="hello")
    captured = {}

    class _LegacyAgent:
        def run_conversation(self, message, conversation_history=None, task_id=None):
            captured.update(message=message, conversation_history=conversation_history, task_id=task_id)
            return {"final_response": "ok", "messages": []}

    turn_runner = TurnRunner(SimpleNamespace(_consume_pending_native_image_paths=lambda _key: []), ctx)
    with (
        patch("gateway.run._wrap_current_message_with_observed_context", side_effect=lambda message, _context: message),
        patch("tools.approval.register_gateway_notify"),
        patch("tools.approval.unregister_gateway_notify"),
        patch("tools.approval_context.set_current_session_key", return_value=object()),
        patch("tools.approval_context.reset_current_session_key"),
        patch("agent.notification_presentation.notification_turn", side_effect=lambda *a, **k: nullcontext()),
    ):
        result = turn_runner._run_conversation_with_approval(_LegacyAgent(), [], None, None, None)

    assert result["final_response"] == "ok"
    assert captured == {"message": "hello", "conversation_history": [], "task_id": "session-1"}
