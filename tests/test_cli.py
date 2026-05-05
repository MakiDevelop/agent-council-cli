from __future__ import annotations

import argparse
import json

from agent_council.audit import latest_session, load_events, write_event
from agent_council.cli import agents_from_args, clean_body, extract_parent_context, resolve_prompt
from agent_council.workers import AgentConfig, build_command, build_prompt, load_agents_config, resolve_agents


def test_clean_body_strips_markdown_noise() -> None:
    out = clean_body("""
    [AGENT: codex]
    # Heading
    | a | b |
    - first
    > quoted
    """)
    assert "[AGENT:" not in out
    assert "|" not in out
    assert "Heading" in out
    assert "first" in out
    assert "quoted" in out


def test_resolve_agents_default_and_custom() -> None:
    agents = load_agents_config(None)
    assert [agent.name for agent in resolve_agents(None, agents)] == ["claude", "codex", "gemini"]
    assert [agent.name for agent in resolve_agents("codex,gemini", agents)] == ["codex", "gemini"]


def test_build_prompt_tags_provider() -> None:
    agent = AgentConfig("codex", ("codex", "{prompt}"), "Role: Engineer.")
    prompt = build_prompt(agent, "review this")
    assert prompt.startswith("[AGENT: codex]")
    assert "review this" in prompt
    assert "Do not modify files" in prompt


def test_build_command_replaces_prompt() -> None:
    agent = AgentConfig("local", ("tool", "--prompt", "{prompt}"), "Role: Local reviewer.")
    assert build_command(agent, "hello") == ["tool", "--prompt", "hello"]


def test_load_agents_config_yaml_subset(tmp_path) -> None:
    path = tmp_path / "agents.yaml"
    path.write_text(
        """
agents:
  local:
    command: ["ollama", "run", "llama3.1", "{prompt}"]
    role: "Local reviewer."
""",
        encoding="utf-8",
    )
    agents = load_agents_config(path)
    assert agents["local"].command == ("ollama", "run", "llama3.1", "{prompt}")
    assert agents["local"].role == "Local reviewer."


def test_agents_from_args_loads_config(tmp_path) -> None:
    path = tmp_path / "agents.yaml"
    path.write_text(
        """
agents:
  local:
    command: ["python", "-c", "print('ok')", "{prompt}"]
    role: "Local reviewer."
""",
        encoding="utf-8",
    )
    ns = argparse.Namespace(config=path, providers="local")
    assert [agent.name for agent in agents_from_args(ns)] == ["local"]


def test_resolve_prompt_from_items() -> None:
    ns = argparse.Namespace(prompt=["hello", "world"], file=None, stdin=False)
    assert resolve_prompt(ns) == "hello world"


def test_audit_roundtrip(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("AGENT_COUNCIL_AUDIT_DIR", str(tmp_path))
    write_event("trace-test", {"event": "session_created"})
    write_event("trace-test", {"event": "worker_result", "provider": "codex", "stdout": "ok"})
    events = load_events("test")
    assert [event["event"] for event in events] == ["session_created", "worker_result"]
    assert latest_session() == "test"


def test_extract_parent_context() -> None:
    events = [{"event": "worker_result", "provider": "codex", "stdout": "[AGENT: codex] ok"}]
    assert "## codex" in extract_parent_context(events)
    assert "ok" in extract_parent_context(events)


def test_watch_events_are_json_serializable() -> None:
    event = {"event": "worker_result", "provider": "gemini", "stdout": "ok"}
    assert json.loads(json.dumps(event))["provider"] == "gemini"
