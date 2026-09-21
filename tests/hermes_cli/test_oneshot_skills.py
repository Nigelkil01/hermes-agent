"""Regression tests: -z/--oneshot must honor -s/--skills (#31548, #65119).

The oneshot path builds its AIAgent directly (bypassing HermesCLI), so the
--skills preload has to be forwarded explicitly and injected via
``ephemeral_system_prompt``. These tests pin the forwarding contract and the
partial-success semantics shared with normal CLI chat.
"""

import pytest

from hermes_cli.oneshot import _build_preloaded_skills_prompt, _normalize_skills


class TestNormalizeSkills:
    def test_none_and_empty(self):
        assert _normalize_skills(None) == []
        assert _normalize_skills("") == []
        assert _normalize_skills([]) == []

    def test_comma_separated_string(self):
        assert _normalize_skills("a,b") == ["a", "b"]

    def test_repeated_flags_deduped_order_preserved(self):
        assert _normalize_skills(["b", "a", "b"]) == ["b", "a"]


class TestBuildPreloadedSkillsPrompt:
    def test_no_skills_returns_none(self):
        assert _build_preloaded_skills_prompt(None) is None

    def test_all_missing_raises(self, monkeypatch):
        import agent.skill_commands as sc

        monkeypatch.setattr(
            sc, "build_preloaded_skills_prompt",
            lambda parsed, **kw: ("", [], list(parsed)),
        )
        with pytest.raises(ValueError, match="Unknown skill"):
            _build_preloaded_skills_prompt("not-a-skill")

    def test_partial_success_returns_prompt(self, monkeypatch):
        import agent.skill_commands as sc

        monkeypatch.setattr(
            sc, "build_preloaded_skills_prompt",
            lambda parsed, **kw: ("PROMPT", ["good"], ["bad"]),
        )
        assert _build_preloaded_skills_prompt(["good", "bad"]) == "PROMPT"

    def test_loaded_prompt_returned(self, monkeypatch):
        import agent.skill_commands as sc

        monkeypatch.setattr(
            sc, "build_preloaded_skills_prompt",
            lambda parsed, **kw: ("SKILL CONTENT", ["s"], []),
        )
        assert _build_preloaded_skills_prompt("s") == "SKILL CONTENT"


class TestSkillsWiring:
    """The preload contract only matters if -s actually reaches the agent. These pin the
    three hops: argv → ``run_oneshot(skills=...)``, ``run_oneshot`` → ``_run_agent``, and
    ``_run_agent`` → ``AIAgent(ephemeral_system_prompt=<built prompt>)``."""

    def test_top_level_z_forwards_skills_flag(self, monkeypatch):
        import hermes_cli.main as main_mod
        from hermes_cli._parser import build_top_level_parser

        captured = {}
        monkeypatch.setattr(main_mod, "_confirm_startup_expensive_model_override", lambda _a: None)
        monkeypatch.setattr(main_mod, "_resolve_chat_session_args", lambda _a, use_tui: None)
        monkeypatch.setattr(main_mod, "_cleanup_oneshot_runtime", lambda: None)
        monkeypatch.setattr(main_mod, "_exit_after_oneshot", lambda rc: captured.update(rc=rc))
        monkeypatch.setattr(
            "hermes_cli.oneshot.run_oneshot",
            lambda prompt, **kw: captured.update(prompt=prompt, **kw) or 0,
        )

        args = build_top_level_parser()[0].parse_args(["-z", "hello", "-s", "a", "--skills", "b,c"])
        main_mod._run_oneshot_from_args(args)

        assert captured["rc"] == 0
        assert captured["prompt"] == "hello"
        assert captured["skills"] == ["a", "b,c"]

    def test_run_oneshot_forwards_skills_to_run_agent(self, monkeypatch):
        from hermes_cli.oneshot import run_oneshot

        captured = {}

        def _fake_run_agent(prompt, **kwargs):
            captured.update(kwargs, prompt=prompt)
            return "ok", {"final_response": "ok"}

        monkeypatch.setattr("hermes_cli.oneshot._run_agent", _fake_run_agent)
        assert run_oneshot("hello", skills=["demo-skill"]) == 0
        assert captured["prompt"] == "hello"
        assert captured["skills"] == ["demo-skill"]

    def test_run_agent_injects_skills_prompt_as_ephemeral_system_prompt(self, monkeypatch):
        import agent.skill_commands as sc
        import hermes_cli.oneshot as oneshot_mod

        captured = {}

        class _FakeAgent:
            def __init__(self, **kwargs):
                captured.update(kwargs)
            def __setattr__(self, name, _value):
                pass
            def run_conversation(self, _prompt, conversation_history=None):
                return {"final_response": "ok"}
            def close(self):
                pass

        monkeypatch.setattr(
            sc, "build_preloaded_skills_prompt",
            lambda parsed, **kw: (f"SKILL PROMPT for {','.join(parsed)}", list(parsed), []),
        )
        monkeypatch.setattr("hermes_cli.config.load_config", lambda: {"model": {"default": "m", "provider": "openrouter"}})
        monkeypatch.setattr(
            "hermes_cli.runtime_provider.resolve_runtime_provider",
            lambda **_kw: {"api_key": "k", "base_url": None, "provider": "openrouter",
                          "requested_provider": "openrouter", "api_mode": "chat", "credential_pool": None})
        monkeypatch.setattr("hermes_cli.tools_config._get_platform_tools", lambda _cfg, _p: [])
        monkeypatch.setattr("hermes_cli.mcp_startup.ensure_mcp_discovery_before_agent_build", lambda **_kw: None)
        monkeypatch.setattr("run_agent.AIAgent", _FakeAgent)

        text, _result = oneshot_mod._run_agent("hello", skills="demo-skill,other")
        assert text == "ok"
        assert captured["ephemeral_system_prompt"] == "SKILL PROMPT for demo-skill,other"

        captured.clear()
        oneshot_mod._run_agent("hello")
        assert captured["ephemeral_system_prompt"] is None
