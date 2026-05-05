from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class MemoryCandidate:
    session_id: str
    source_agent: str
    target_namespace: str
    memory_type: str
    confidence: float
    reason: str
    text: str
    status: str = "candidate"

    def to_record(self) -> dict[str, Any]:
        return asdict(self)


def clean_memory_text(text: str, max_lines: int = 10, max_chars: int = 1200) -> str:
    lines: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("[AGENT:"):
            continue
        if line.startswith("|"):
            continue
        line = line.lstrip("#").strip().lstrip("-*•>").strip()
        if line:
            lines.append(line)
        if len(lines) >= max_lines:
            break
    body = "\n".join(lines)
    return body[:max_chars].rstrip()


def memory_type_for_agent(agent: str) -> tuple[str, str]:
    name = agent.lower()
    if "claude" in name:
        return "architecture", "Claude-like agents are routed to architecture and design memory."
    if "codex" in name:
        return "implementation", "Codex-like agents are routed to implementation and validation memory."
    if "gemini" in name:
        return "analysis", "Gemini-like agents are routed to analysis, alternatives, and tradeoff memory."
    if "ollama" in name or "llama" in name or "gemma" in name or "local" in name:
        return "local_review", "Local model agents are routed to local-review memory."
    return "agent_note", "Custom agents are routed to their own agent namespace by default."


def confidence_for_text(text: str, *, exit_code: int, timed_out: bool) -> float:
    if timed_out or exit_code != 0:
        return 0.0
    score = 0.45
    lowered = text.lower()
    if len(text) >= 240:
        score += 0.15
    if any(word in lowered for word in ["recommendation", "decision", "risk", "tradeoff"]):
        score += 0.15
    if any(word in lowered for word in ["test", "verify", "implementation", "architecture"]):
        score += 0.1
    if "unknown" in lowered or "not sure" in lowered:
        score -= 0.1
    return max(0.0, min(score, 0.9))


def build_memory_candidates(
    events: list[dict[str, Any]],
    *,
    project: str | None = None,
    min_confidence: float = 0.5,
) -> list[MemoryCandidate]:
    session = next(
        (event.get("session_id") for event in events if event.get("event") == "session_created"),
        "unknown",
    )
    candidates: list[MemoryCandidate] = []
    for event in events:
        if event.get("event") != "worker_result":
            continue
        agent = str(event.get("provider") or "unknown")
        body = str(event.get("stdout") or event.get("stderr") or "")
        text = clean_memory_text(body)
        if not text:
            continue
        exit_code = int(event.get("exit_code") or 0)
        timed_out = bool(event.get("timed_out"))
        confidence = confidence_for_text(text, exit_code=exit_code, timed_out=timed_out)
        if confidence < min_confidence:
            continue
        memory_type, reason = memory_type_for_agent(agent)
        candidates.append(
            MemoryCandidate(
                session_id=str(session),
                source_agent=agent,
                target_namespace=f"agent:{agent}",
                memory_type=memory_type,
                confidence=round(confidence, 2),
                reason=reason,
                text=text,
            )
        )
        if project:
            candidates.append(
                MemoryCandidate(
                    session_id=str(session),
                    source_agent=agent,
                    target_namespace=f"project:{project}",
                    memory_type=memory_type,
                    confidence=round(max(confidence - 0.1, 0.0), 2),
                    reason="Project-scoped copy for later human review; not written automatically.",
                    text=text,
                )
            )
    return candidates


def format_candidates_jsonl(candidates: list[MemoryCandidate]) -> str:
    return "\n".join(json.dumps(c.to_record(), ensure_ascii=False) for c in candidates)


def format_candidates_memhall_jsonl(candidates: list[MemoryCandidate]) -> str:
    records: list[dict[str, Any]] = []
    for candidate in candidates:
        records.append({
            "agent_id": candidate.source_agent,
            "namespace": candidate.target_namespace,
            "type": candidate.memory_type,
            "content": candidate.text,
            "summary": candidate.text.splitlines()[0][:160] if candidate.text else None,
            "tags": ["agent-council", "memory-candidate", candidate.memory_type],
            "references": [f"agent-council:{candidate.session_id}"],
            "metadata": {
                "source": "agent-council-cli",
                "status": candidate.status,
                "confidence": candidate.confidence,
                "reason": candidate.reason,
            },
        })
    return "\n".join(json.dumps(record, ensure_ascii=False) for record in records)


def format_candidates_mem0_jsonl(candidates: list[MemoryCandidate]) -> str:
    records: list[dict[str, Any]] = []
    for candidate in candidates:
        records.append({
            "messages": [{"role": "assistant", "content": candidate.text}],
            "user_id": candidate.target_namespace,
            "metadata": {
                "source": "agent-council-cli",
                "session_id": candidate.session_id,
                "source_agent": candidate.source_agent,
                "memory_type": candidate.memory_type,
                "status": candidate.status,
                "confidence": candidate.confidence,
                "reason": candidate.reason,
            },
        })
    return "\n".join(json.dumps(record, ensure_ascii=False) for record in records)


def format_candidates_markdown(candidates: list[MemoryCandidate]) -> str:
    if not candidates:
        return "No memory candidates found."
    lines = ["# Memory Candidates", ""]
    for i, candidate in enumerate(candidates, start=1):
        lines.extend([
            f"## {i}. {candidate.target_namespace}",
            "",
            f"- source_agent: `{candidate.source_agent}`",
            f"- memory_type: `{candidate.memory_type}`",
            f"- confidence: `{candidate.confidence}`",
            f"- status: `{candidate.status}`",
            f"- reason: {candidate.reason}",
            "",
            "```text",
            candidate.text,
            "```",
            "",
        ])
    return "\n".join(lines).rstrip()
