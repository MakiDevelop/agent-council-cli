from __future__ import annotations

import argparse
import json

from agent_council.audit import latest_session, load_events, write_event
from agent_council.cli import clean_body, extract_parent_context, provider_list, resolve_prompt
from agent_council.workers import Provider, build_prompt


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


def test_provider_list_default_and_custom() -> None:
    assert provider_list(None) == (Provider.claude, Provider.codex, Provider.gemini)
    assert provider_list("codex,gemini") == (Provider.codex, Provider.gemini)


def test_build_prompt_tags_provider() -> None:
    prompt = build_prompt(Provider.codex, "review this")
    assert prompt.startswith("[AGENT: codex]")
    assert "review this" in prompt
    assert "Do not modify files" in prompt


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
