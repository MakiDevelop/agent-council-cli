from __future__ import annotations

import argparse
import textwrap


RESPONSES = {
    "claude-mock": """
    # Claude Mock

    Recommendation: add Redis only after measuring the slow path.

    The current API probably needs clearer cache boundaries first. Start with
    endpoint latency, cache invalidation rules, and a fallback path when Redis is
    unavailable. Redis is a good fit for shared rate-limit counters and hot
    read-heavy objects, but it should not become the source of truth.
    """,
    "codex-mock": """
    # Codex Mock

    Recommendation: do not add Redis yet.

    The implementation risk is cache invalidation and test complexity. First add
    request timing, database query metrics, and a small in-process cache behind
    one interface. If p95 latency is still high, add Redis with integration tests
    for expiry, stale reads, and outage behavior.
    """,
    "gemini-mock": """
    # Gemini Mock

    Recommendation: use Redis for rate limiting, not broad response caching.

    The strongest case is centralized counters across API instances. The weaker
    case is generic response caching, because user-specific data and freshness
    rules can make correctness harder than the latency win. Consider a narrow
    Redis rollout with observability and a kill switch.
    """,
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--agent", required=True, choices=sorted(RESPONSES))
    parser.add_argument("prompt")
    args = parser.parse_args()

    print(f"[AGENT: {args.agent}]")
    print(f"Prompt received: {args.prompt.splitlines()[-1]}")
    print(textwrap.dedent(RESPONSES[args.agent]).strip())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
