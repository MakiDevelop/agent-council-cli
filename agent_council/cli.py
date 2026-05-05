from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from .audit import audit_dir, audit_file, latest_session, load_events, session_id, trace_id, write_event
from .memory import (
    build_memory_candidates,
    format_candidates_jsonl,
    format_candidates_markdown,
    format_candidates_mem0_jsonl,
    format_candidates_memhall_jsonl,
)
from .workers import (
    AgentConfig,
    WorkerResult,
    WorkerSpec,
    build_prompt,
    load_agents_config,
    resolve_agents,
    run_worker,
)


def make_session_id(prefix: str, prompt: str) -> str:
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    h = hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:6]
    return f"{prefix}-{ts}-{h}"


def resolve_prompt(args: argparse.Namespace, field: str = "prompt") -> str:
    if getattr(args, "file", None):
        return args.file.read_text(encoding="utf-8")
    if getattr(args, "stdin", False):
        return sys.stdin.read()
    value = getattr(args, field, "")
    if isinstance(value, list):
        return " ".join(value)
    return value or ""


def agents_from_args(args: argparse.Namespace) -> tuple[AgentConfig, ...]:
    config = load_agents_config(getattr(args, "config", None))
    return resolve_agents(getattr(args, "providers", None), config)


def clean_body(text: str, max_lines: int = 8, max_chars: int = 900) -> str:
    lines: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("[AGENT:"):
            _, sep, rest = line.partition("]")
            line = rest.strip() if sep else line
        if not line or line.startswith("|"):
            continue
        line = line.lstrip("#").strip().lstrip("-*•>").strip()
        if line:
            lines.append(line)
        if len(lines) >= max_lines:
            break
    body = "\n".join(lines) if lines else "(no readable summary)"
    return body[:max_chars].rstrip() + ("\n[truncated]" if len(body) > max_chars else "")


def format_result(session: str, results: list[WorkerResult]) -> str:
    lines = ["-" * 72, f"session {session}  workers={len(results)}"]
    for result in results:
        lines.append("")
        lines.append(f"{result.provider}:")
        body = result.stdout.strip() or result.stderr.strip() or f"<empty output, exit={result.exit_code}>"
        for line in clean_body(body).splitlines():
            lines.append(f"  {line}")
    lines.append("-" * 72)
    return "\n".join(lines)


def extract_parent_context(events: list[dict[str, Any]]) -> str:
    chunks: list[str] = []
    for event in events:
        if event.get("event") != "worker_result":
            continue
        provider = event.get("provider", "unknown")
        body = event.get("stdout") or event.get("stderr") or ""
        if body:
            chunks.append(f"## {provider}\n{body[:4000]}")
    return "\n\n".join(chunks) if chunks else "[No previous worker results found.]"


async def run_council(
    prompt: str,
    *,
    agents: tuple[AgentConfig, ...],
    timeout_sec: int,
    cwd: Path,
    parent_session: str | None = None,
    quiet: bool = False,
) -> str:
    if not prompt.strip():
        raise ValueError("prompt must be non-empty")
    session = make_session_id("cont" if parent_session else "ask", prompt)
    trace = trace_id(session)
    write_event(trace, {
        "event": "session_created",
        "session_id": session,
        "parent_session_id": parent_session,
        "prompt": prompt,
    })
    if not quiet:
        print(f"session: {session}", file=sys.stderr)
        print(f"audit  : {audit_file(session)}", file=sys.stderr)

    def emit(payload: dict[str, Any]) -> None:
        write_event(trace, payload)
        if not quiet and payload.get("event") == "worker_complete":
            print(
                f"[{payload.get('provider')}] complete {payload.get('elapsed_sec', 0):.1f}s",
                file=sys.stderr,
            )

    specs = [
        WorkerSpec(agent=a, prompt=build_prompt(a, prompt), cwd=cwd, timeout_sec=timeout_sec, event_callback=emit)
        for a in agents
    ]
    results = await asyncio.gather(*(run_worker(spec) for spec in specs))
    for result in results:
        write_event(trace, {
            "event": "worker_result",
            "provider": result.provider,
            "exit_code": result.exit_code,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "elapsed_sec": result.elapsed_sec,
            "timed_out": result.timed_out,
        })
    write_event(trace, {"event": "session_complete", "session_id": session})
    print(format_result(session, list(results)))
    return session


async def ask(args: argparse.Namespace) -> int:
    await run_council(
        resolve_prompt(args),
        agents=agents_from_args(args),
        timeout_sec=args.timeout,
        cwd=args.cwd.resolve(),
        quiet=args.quiet,
    )
    return 0


async def continue_cmd(args: argparse.Namespace) -> int:
    parent = args.session or latest_session()
    if parent is None:
        print(f"No previous sessions in {audit_dir()}", file=sys.stderr)
        return 4
    prompt = resolve_prompt(args, "items")
    events = load_events(parent)
    follow_up = "\n\n".join([
        f"Previous session: {parent}",
        "Previous council outputs:",
        extract_parent_context(events),
        "---",
        "Follow-up:",
        prompt,
    ])
    await run_council(
        follow_up,
        agents=agents_from_args(args),
        timeout_sec=args.timeout,
        cwd=args.cwd.resolve(),
        parent_session=session_id(trace_id(parent)),
        quiet=args.quiet,
    )
    return 0


def sessions(args: argparse.Namespace) -> int:
    root = audit_dir()
    if not root.exists():
        print(f"No sessions in {root}")
        return 0
    files = sorted(root.glob("trace-*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
    for path in files[: args.limit]:
        print(session_id(path.stem))
    return 0


def status(args: argparse.Namespace) -> int:
    session = args.session or latest_session()
    if session is None:
        print(f"No sessions in {audit_dir()}", file=sys.stderr)
        return 4
    events = load_events(session)
    parent = next((e.get("parent_session_id") for e in events if e.get("event") == "session_created"), None)
    print(f"session: {session_id(trace_id(session))}")
    if parent:
        print(f"parent : {parent}")
    print(f"events : {len(events)}")
    print(f"last   : {events[-1].get('event') if events else 'empty'}")
    return 0


def watch(args: argparse.Namespace) -> int:
    session = args.session or latest_session()
    if session is None:
        print(f"No sessions in {audit_dir()}", file=sys.stderr)
        return 4
    for event in load_events(session):
        print(json.dumps(event, ensure_ascii=False))
    return 0


def memory_candidates(args: argparse.Namespace) -> int:
    session = args.session or latest_session()
    if session is None:
        print(f"No sessions in {audit_dir()}", file=sys.stderr)
        return 4
    events = load_events(session)
    candidates = build_memory_candidates(
        events,
        project=args.project,
        min_confidence=args.min_confidence,
    )
    if args.format == "jsonl":
        output = format_candidates_jsonl(candidates)
    elif args.format == "memhall-jsonl":
        output = format_candidates_memhall_jsonl(candidates)
    elif args.format == "mem0-jsonl":
        output = format_candidates_mem0_jsonl(candidates)
    else:
        output = format_candidates_markdown(candidates)
    if args.out:
        args.out.write_text(output + ("\n" if output else ""), encoding="utf-8")
    else:
        print(output)
    return 0


CHAT_HELP = """Commands:
  /help              Show this help
  /status            Show current session status
  /sessions          List recent sessions
  /watch             Print current session audit events
  /use <session_id>  Switch current session
  /new <prompt>      Start a new thread
  /exit              Exit
"""


async def chat(args: argparse.Namespace) -> int:
    current: str | None = None
    agents = agents_from_args(args)
    initial = " ".join(args.prompt).strip()
    print("agent-council chat")
    print("Type /help for commands, /exit to quit.")
    if initial:
        current = await run_council(
            initial,
            agents=agents,
            timeout_sec=args.timeout,
            cwd=args.cwd.resolve(),
            quiet=args.quiet,
        )
    while True:
        try:
            line = input(f"agent-council[{current or 'new'}]> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if not line:
            continue
        if line in {"/exit", "/quit"}:
            return 0
        if line == "/help":
            print(CHAT_HELP)
            continue
        if line == "/sessions":
            sessions(argparse.Namespace(limit=10))
            continue
        if line == "/status":
            status(argparse.Namespace(session=current))
            continue
        if line == "/watch":
            watch(argparse.Namespace(session=current))
            continue
        if line.startswith("/use "):
            current = line.removeprefix("/use ").strip()
            print(f"current session: {current}")
            continue
        if line.startswith("/new "):
            current = await run_council(
                line.removeprefix("/new ").strip(),
                agents=agents,
                timeout_sec=args.timeout,
                cwd=args.cwd.resolve(),
                quiet=args.quiet,
            )
            continue
        if current:
            parent_events = load_events(current)
            prompt = "\n\n".join([
                f"Previous session: {current}",
                "Previous council outputs:",
                extract_parent_context(parent_events),
                "---",
                "Follow-up:",
                line,
            ])
            current = await run_council(
                prompt,
                agents=agents,
                timeout_sec=args.timeout,
                cwd=args.cwd.resolve(),
                parent_session=current,
                quiet=args.quiet,
            )
        else:
            current = await run_council(
                line,
                agents=agents,
                timeout_sec=args.timeout,
                cwd=args.cwd.resolve(),
                quiet=args.quiet,
            )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="agent-council")
    sub = parser.add_subparsers(dest="cmd", required=True)

    def add_common(p: argparse.ArgumentParser) -> None:
        p.add_argument("--config", type=Path, help="Path to agents.yaml or agents.json")
        p.add_argument("--providers", help="Comma-separated agent names from built-ins or config")
        p.add_argument("--timeout", type=int, default=900)
        p.add_argument("--cwd", type=Path, default=Path.cwd())
        p.add_argument("--quiet", action="store_true")

    ask_p = sub.add_parser("ask", help="Ask multiple CLI agents")
    ask_src = ask_p.add_mutually_exclusive_group(required=True)
    ask_src.add_argument("prompt", nargs="?")
    ask_src.add_argument("-f", "--file", type=Path)
    ask_src.add_argument("--stdin", action="store_true")
    add_common(ask_p)

    cont_p = sub.add_parser("continue", help="Continue the latest or selected session")
    cont_p.add_argument("items", nargs="*")
    cont_p.add_argument("--session")
    cont_p.add_argument("-f", "--file", type=Path)
    cont_p.add_argument("--stdin", action="store_true")
    add_common(cont_p)

    chat_p = sub.add_parser("chat", help="Open an Ollama-style chat loop")
    chat_p.add_argument("prompt", nargs="*")
    add_common(chat_p)

    sessions_p = sub.add_parser("sessions")
    sessions_p.add_argument("--limit", type=int, default=20)

    status_p = sub.add_parser("status")
    status_p.add_argument("session", nargs="?")

    watch_p = sub.add_parser("watch")
    watch_p.add_argument("session", nargs="?")

    mem_p = sub.add_parser("memory-candidates", help="Classify audit logs into memory candidates")
    mem_p.add_argument("session", nargs="?")
    mem_p.add_argument("--project", help="Also emit project:<name> candidates")
    mem_p.add_argument(
        "--format",
        choices=("jsonl", "markdown", "memhall-jsonl", "mem0-jsonl"),
        default="markdown",
    )
    mem_p.add_argument("--min-confidence", type=float, default=0.5)
    mem_p.add_argument("--out", type=Path)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.cmd == "ask":
        return asyncio.run(ask(args))
    if args.cmd == "continue":
        return asyncio.run(continue_cmd(args))
    if args.cmd == "chat":
        return asyncio.run(chat(args))
    if args.cmd == "sessions":
        return sessions(args)
    if args.cmd == "status":
        return status(args)
    if args.cmd == "watch":
        return watch(args)
    if args.cmd == "memory-candidates":
        return memory_candidates(args)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
