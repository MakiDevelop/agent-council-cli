# agent-council-cli

Prompt-native multi-agent validation loop for Claude, Codex, and Gemini CLIs.

This is not an autonomous agent swarm. It is a small command-line harness for
asking multiple CLI agents the same question, comparing their answers, and
keeping an append-only audit trail.

## Why

Most multi-agent demos optimize for automation. This project optimizes for a
human workflow:

- keep natural-language prompting as the main interface
- run multiple strong CLI agents in parallel
- give each agent a distinct review role
- show a compact human-readable summary by default
- keep raw transcripts in JSONL for later debugging
- support threaded follow-up without requiring a daemon or web app

## Install

```bash
git clone https://github.com/MakiDevelop/agent-council-cli.git
cd agent-council-cli
python -m pip install -e ".[dev]"
```

You also need the provider CLIs you want to use:

- `claude`
- `codex`
- `gemini`

Each provider uses its own CLI authentication. The harness strips common API key
environment variables from worker subprocesses by default.

## Usage

Ask all default providers:

```bash
agent-council ask "Review this architecture and identify the top risks."
```

Use a subset:

```bash
agent-council ask "Review this plan" --providers codex,gemini
```

Continue the latest session:

```bash
agent-council continue "Turn that into a concrete implementation plan."
```

Open an Ollama-style chat loop:

```bash
agent-council chat
agent-council chat "Start by reviewing this idea."
```

Inside chat:

```text
/status
/sessions
/watch
/use <session_id>
/new <prompt>
/exit
```

Inspect audit data:

```bash
agent-council sessions
agent-council status
agent-council watch
```

Audit logs are stored in:

```text
.agent-council/audit/
```

Override with:

```bash
export AGENT_COUNCIL_AUDIT_DIR=/path/to/audit
```

## Design

The default roles are:

- Claude: architect reviewer
- Codex: engineer and dissenter
- Gemini: analyst

The default output is intentionally compact. Raw stdout/stderr and event details
remain available through `agent-council watch`.

## Safety

This project is designed for validation and review. The shared prompt tells
providers not to modify files. Provider CLIs still have their own behavior and
permissions, so run this in a repository or directory where you are comfortable
running those tools.

## Development

```bash
pytest
ruff check .
python -m agent_council chat
```

## License

MIT
