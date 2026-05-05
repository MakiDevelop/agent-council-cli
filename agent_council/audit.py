from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ENV_AUDIT_DIR = "AGENT_COUNCIL_AUDIT_DIR"


def audit_dir() -> Path:
    override = os.environ.get(ENV_AUDIT_DIR)
    if override:
        return Path(override).expanduser().resolve()
    return (Path.cwd() / ".agent-council" / "audit").resolve()


def trace_id(session_id: str) -> str:
    return session_id if session_id.startswith("trace-") else f"trace-{session_id}"


def session_id(trace: str) -> str:
    return trace.removeprefix("trace-")


def audit_file(session: str) -> Path:
    return audit_dir() / f"{trace_id(session)}.jsonl"


def write_event(trace: str, payload: dict[str, Any]) -> None:
    target_dir = audit_dir()
    target_dir.mkdir(parents=True, exist_ok=True)
    record = {"ts": datetime.now(timezone.utc).isoformat(), **payload}
    with (target_dir / f"{trace_id(trace)}.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False, default=str))
        f.write("\n")


def load_events(session: str) -> list[dict[str, Any]]:
    path = audit_file(session)
    if not path.exists():
        raise FileNotFoundError(path)
    events: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            events.append({"event": "malformed_line", "raw": line})
    return events


def latest_session() -> str | None:
    root = audit_dir()
    if not root.exists():
        return None
    files = sorted(root.glob("trace-*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
    return session_id(files[0].stem) if files else None
