from __future__ import annotations

import asyncio
import os
import shutil
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable


class Provider(str, Enum):
    claude = "claude"
    codex = "codex"
    gemini = "gemini"


ROLE_PROMPTS: dict[Provider, str] = {
    Provider.claude: (
        "Role: Architect reviewer. Focus on system design, long-term maintainability, "
        "and integration risks."
    ),
    Provider.codex: (
        "Role: Engineer and dissenter. Focus on implementation feasibility, tests, "
        "edge cases, rollback, and concrete risks."
    ),
    Provider.gemini: (
        "Role: Analyst. Focus on alternatives, missing evidence, comparisons, and "
        "confidence levels."
    ),
}


READ_ONLY_DIRECTIVE = (
    "You are running as a validation worker. Do not modify files, commit, push, deploy, "
    "or claim to have used tools you did not actually use. If unsure, say UNKNOWN."
)


@dataclass(frozen=True, slots=True)
class WorkerSpec:
    provider: Provider
    prompt: str
    cwd: Path
    timeout_sec: int = 900
    event_callback: Callable[[dict[str, Any]], None] | None = field(default=None, repr=False)


@dataclass(slots=True)
class WorkerResult:
    provider: Provider
    exit_code: int
    stdout: str
    stderr: str
    elapsed_sec: float
    timed_out: bool = False


def build_prompt(provider: Provider, user_prompt: str) -> str:
    return "\n\n".join([
        f"[AGENT: {provider.value}]",
        ROLE_PROMPTS[provider],
        READ_ONLY_DIRECTIVE,
        "---",
        user_prompt.strip(),
    ])


def build_command(provider: Provider, prompt: str) -> list[str]:
    if provider is Provider.claude:
        return ["claude", "--print", prompt]
    if provider is Provider.codex:
        return [
            "codex",
            "exec",
            "--sandbox",
            "read-only",
            "--skip-git-repo-check",
            prompt,
        ]
    if provider is Provider.gemini:
        return ["gemini", "-p", prompt, "-o", "text"]
    raise ValueError(f"unsupported provider: {provider}")


def safe_env() -> dict[str, str]:
    blocked = {"ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY"}
    env = {k: v for k, v in os.environ.items() if k not in blocked}
    env["TERM"] = "dumb"
    return env


async def run_worker(spec: WorkerSpec) -> WorkerResult:
    if shutil.which(spec.provider.value) is None:
        return WorkerResult(spec.provider, 127, "", f"binary not found: {spec.provider.value}", 0.0)

    argv = build_command(spec.provider, spec.prompt)
    start = time.monotonic()

    def emit(payload: dict[str, Any]) -> None:
        if spec.event_callback:
            spec.event_callback({"provider": spec.provider.value, **payload})

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
        provider=spec.provider,
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
