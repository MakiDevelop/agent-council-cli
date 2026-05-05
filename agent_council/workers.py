from __future__ import annotations

import asyncio
import json
import os
import shlex
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable


READ_ONLY_DIRECTIVE = (
    "You are running as a validation worker. Do not modify files, commit, push, deploy, "
    "or claim to have used tools you did not actually use. If unsure, say UNKNOWN."
)


@dataclass(frozen=True, slots=True)
class AgentConfig:
    name: str
    command: tuple[str, ...]
    role: str


@dataclass(frozen=True, slots=True)
class WorkerSpec:
    agent: AgentConfig
    prompt: str
    cwd: Path
    timeout_sec: int = 900
    event_callback: Callable[[dict[str, Any]], None] | None = field(default=None, repr=False)


@dataclass(slots=True)
class WorkerResult:
    agent: AgentConfig
    exit_code: int
    stdout: str
    stderr: str
    elapsed_sec: float
    timed_out: bool = False

    @property
    def provider(self) -> str:
        return self.agent.name


BUILTIN_AGENTS: dict[str, AgentConfig] = {
    "claude": AgentConfig(
        name="claude",
        command=("claude", "--print", "{prompt}"),
        role=(
            "Role: Architect reviewer. Focus on system design, long-term maintainability, "
            "and integration risks."
        ),
    ),
    "codex": AgentConfig(
        name="codex",
        command=(
            "codex",
            "exec",
            "--sandbox",
            "read-only",
            "--skip-git-repo-check",
            "{prompt}",
        ),
        role=(
            "Role: Engineer and dissenter. Focus on implementation feasibility, tests, "
            "edge cases, rollback, and concrete risks."
        ),
    ),
    "gemini": AgentConfig(
        name="gemini",
        command=("gemini", "-p", "{prompt}", "-o", "text"),
        role=(
            "Role: Analyst. Focus on alternatives, missing evidence, comparisons, and "
            "confidence levels."
        ),
    ),
}


def build_prompt(agent: AgentConfig, user_prompt: str) -> str:
    return "\n\n".join([
        f"[AGENT: {agent.name}]",
        agent.role,
        READ_ONLY_DIRECTIVE,
        "---",
        user_prompt.strip(),
    ])


def build_command(agent: AgentConfig, prompt: str) -> list[str]:
    return [part.replace("{prompt}", prompt) for part in agent.command]


def _parse_scalar(value: str) -> str:
    return value.strip().strip('"').strip("'")


def _parse_command(value: str) -> tuple[str, ...]:
    text = value.strip()
    if text.startswith("["):
        parsed = json.loads(text)
        if not isinstance(parsed, list) or not all(isinstance(x, str) for x in parsed):
            raise ValueError("command must be a list of strings")
        return tuple(parsed)
    return tuple(shlex.split(text))


def load_agents_config(path: Path | None) -> dict[str, AgentConfig]:
    agents = dict(BUILTIN_AGENTS)
    if path is None:
        return agents
    if not path.exists():
        raise FileNotFoundError(path)

    data = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json":
        raw = json.loads(data)
        for name, item in raw.get("agents", raw).items():
            agents[name] = AgentConfig(
                name=name,
                command=tuple(item["command"]),
                role=item.get("role", f"Role: {name} reviewer."),
            )
        return agents

    current_name: str | None = None
    current: dict[str, str] = {}

    def flush() -> None:
        nonlocal current_name, current
        if not current_name:
            return
        if "command" not in current:
            raise ValueError(f"agent {current_name!r} missing command")
        agents[current_name] = AgentConfig(
            name=current_name,
            command=_parse_command(current["command"]),
            role=_parse_scalar(current.get("role", f"Role: {current_name} reviewer.")),
        )
        current_name = None
        current = {}

    for raw_line in data.splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or stripped == "agents:":
            continue
        if stripped.endswith(":"):
            flush()
            current_name = stripped[:-1]
            continue
        if current_name and ":" in stripped:
            key, _, value = stripped.partition(":")
            current[key.strip()] = value.strip()
            continue
        raise ValueError(f"unsupported config line: {raw_line!r}")
    flush()
    return agents


def resolve_agents(value: str | None, agents: dict[str, AgentConfig]) -> tuple[AgentConfig, ...]:
    names = ["claude", "codex", "gemini"] if not value else [p.strip() for p in value.split(",")]
    resolved: list[AgentConfig] = []
    for name in names:
        if name not in agents:
            raise ValueError(f"unknown agent {name!r}; available: {', '.join(sorted(agents))}")
        resolved.append(agents[name])
    return tuple(resolved)


def safe_env() -> dict[str, str]:
    blocked = {"ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY"}
    env = {k: v for k, v in os.environ.items() if k not in blocked}
    env["TERM"] = "dumb"
    return env


async def run_worker(spec: WorkerSpec) -> WorkerResult:
    binary = spec.agent.command[0]
    if shutil.which(binary) is None:
        return WorkerResult(spec.agent, 127, "", f"binary not found: {binary}", 0.0)

    argv = build_command(spec.agent, spec.prompt)
    start = time.monotonic()

    def emit(payload: dict[str, Any]) -> None:
        if spec.event_callback:
            spec.event_callback({"provider": spec.agent.name, **payload})

    process = await asyncio.create_subprocess_exec(
        *argv,
        cwd=str(spec.cwd),
        env=safe_env(),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        start_new_session=True,
    )
    emit({"event": "worker_spawned", "pid": process.pid})

    async def read_stream(stream: asyncio.StreamReader | None, stream_name: str) -> str:
        if stream is None:
            return ""
        chunks: list[str] = []
        while True:
            data = await stream.readline()
            if not data:
                break
            text = data.decode("utf-8", errors="replace")
            chunks.append(text)
            emit({"event": "worker_output", "stream": stream_name, "text": text.rstrip("\n")})
        return "".join(chunks)

    stdout_task = asyncio.create_task(read_stream(process.stdout, "stdout"))
    stderr_task = asyncio.create_task(read_stream(process.stderr, "stderr"))
    timed_out = False
    try:
        await asyncio.wait_for(process.wait(), timeout=spec.timeout_sec)
    except asyncio.TimeoutError:
        timed_out = True
        emit({"event": "worker_timeout"})
        process.terminate()
        try:
            await asyncio.wait_for(process.wait(), timeout=5)
        except asyncio.TimeoutError:
            process.kill()

    stdout, stderr = await asyncio.gather(stdout_task, stderr_task)
    elapsed = time.monotonic() - start
    result = WorkerResult(
        agent=spec.agent,
        exit_code=process.returncode if process.returncode is not None else -1,
        stdout=stdout,
        stderr=stderr,
        elapsed_sec=elapsed,
        timed_out=timed_out,
    )
    emit({
        "event": "worker_complete",
        "exit_code": result.exit_code,
        "elapsed_sec": result.elapsed_sec,
        "timed_out": result.timed_out,
    })
    return result
