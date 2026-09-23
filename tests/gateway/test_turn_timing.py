"""Gateway turn timing stays content-free and follows the turn's profile scope."""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from agent import secret_scope
from gateway.config import Platform
from gateway.run_turn import GatewayTurnMixin, logger
from gateway.session import SessionSource
from hermes_constants import get_hermes_home


@pytest.mark.asyncio
async def test_turn_timing_log_follows_profile_a_b_a(tmp_path, monkeypatch):
    root = tmp_path / ".hermes"
    beta = root / "profiles" / "beta"
    beta.mkdir(parents=True)
    monkeypatch.setenv("HERMES_HOME", str(root))
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    seen = []
    logs = []

    class Runner(GatewayTurnMixin):
        config = SimpleNamespace(multiplex_profiles=True)

        def _resolve_profile_home_for_source(self, source):
            return root if source.profile == "default" else beta

        async def _run_agent_inner(self, message, context_prompt, history, source, session_id, **kwargs):
            seen.append(get_hermes_home())
            return {"final_response": "done"}

    def capture_log(format_string, *args):
        logs.append((get_hermes_home(), format_string % args))

    previous = secret_scope.is_multiplex_active()
    secret_scope.set_multiplex_active(True)
    try:
        with patch.object(logger, "info", side_effect=capture_log):
            for profile in ("default", "beta", "default"):
                source = SessionSource(platform=Platform.TELEGRAM, chat_id="chat", chat_type="dm",
                                       thread_id=None, profile=profile)
                await Runner()._run_agent("private message", "", [], source, "session")
    finally:
        secret_scope.set_multiplex_active(previous)

    assert seen == [root, beta, root]
    assert [home for home, _ in logs] == seen
    assert all(message.startswith("gateway agent turn session=session platform=telegram duration_s=")
               for _, message in logs)
    assert all("private message" not in message for _, message in logs)
