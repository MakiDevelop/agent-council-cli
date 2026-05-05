# agent-council-cli

Run the same prompt across the AI CLIs you already use, then compare their
answers.

`agent-council-cli` is a small wrapper for Claude, Codex, Gemini, Ollama, and
custom local commands. It fires one prompt at multiple already-authenticated
CLIs, prints a compact side-by-side result, and keeps the raw transcripts in an
append-only JSONL log.

> Authentication model: users log in to each agent CLI from their own terminal
> first. `agent-council-cli` does not manage OAuth, store API keys, or run
> browser login flows. It only calls local agent CLIs that are already
> authenticated on the user's machine.

## What It Is

- a one-command way to stop copy-pasting the same prompt into multiple AI CLIs
- a side-by-side comparison layer for different model or agent opinions
- a lightweight chat loop when you want follow-up questions
- a JSONL audit log for raw stdout/stderr and session events
- a config file for adding your own local CLI agents

## What It Is Not

- not a tmux, pane, or long-running session manager
- not a git worktree tool
- not an autonomous swarm
- not a multi-agent framework
- not a token or OAuth manager
- not a replacement for Claude Code, Codex, Gemini CLI, or Ollama

## Why

Most multi-agent tools optimize for orchestration. This project optimizes for a
smaller workflow: ask several tools the same question, see the differences, and
decide yourself.

- run multiple strong CLI agents in parallel
- give each agent an optional review role
- show compact output by default
- keep raw transcripts in JSONL for later debugging
- support threaded follow-up without requiring a daemon or web app

## Install

```bash
git clone https://github.com/MakiDevelop/agent-council-cli.git
cd agent-council-cli
python -m pip install -e ".[dev]"
```

You also need the agent CLIs you want to use. The built-ins assume:

- `claude`
- `codex`
- `gemini`

### Authentication

Yes: users should log in to each agent CLI from their own terminal first.
`agent-council` does not manage OAuth, tokens, API keys, or browser login flows.
It only calls local commands that are already authenticated by their own tools.

The harness strips common API key environment variables from worker subprocesses
by default, so provider CLI OAuth, keychain, or local profile state is the
expected path.

## Usage

Ask all default providers:

```bash
agent-council ask "Review this architecture and identify the top risks."
```

Use a subset:

```bash
agent-council ask "Review this plan" --providers codex,gemini
```

Use custom agents:

```bash
agent-council ask "Review this plan" --config agents.yaml --providers security,local-llama
agent-council chat --config agents.yaml --providers local-llama
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

### Custom agents

Custom agents are defined in `agents.yaml`:

```yaml
agents:
  security:
    command: ["my-security-agent", "review", "--prompt", "{prompt}"]
    role: "Role: Security reviewer. Focus on threat modeling and unsafe defaults."

  local-llama:
    command: ["ollama", "run", "llama3.1", "{prompt}"]
    role: "Role: Local reviewer. Be concise and call out uncertainty."
```

`{prompt}` is replaced with the full council prompt. Built-in agents are still
available when a config file is provided, and config entries with the same name
override built-ins.

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

## Roadmap

Near-term ideas:

- `--raw` to show raw provider output without compact formatting
- disagreement-focused output that highlights where agents diverge
- custom summary or judge prompt
- `agent-council doctor` to check installed/authenticated CLIs
- `agent-council agents` to list built-ins and config-loaded agents

Not planned for now:

- worktree management
- tmux dashboards
- agent-to-agent tool calling
- voting systems
- persistent memory
- OAuth or token storage

## 繁體中文快速指南

`agent-council-cli` 是一個小型 CLI wrapper：把同一個 prompt 同時丟給你本機已登入的 Claude、Codex、Gemini、Ollama 或自訂 CLI，並列顯示結果，同時保留可追溯的 JSONL audit log。

它不是 tmux / worktree / dashboard，也不是自動化 agent swarm。它只做一件事：幫你少複製貼上幾次，快速比較不同 AI CLI 的答案。

### 安裝

```bash
git clone https://github.com/MakiDevelop/agent-council-cli.git
cd agent-council-cli
python -m pip install -e ".[dev]"
```

使用前請先在 terminal 裡登入各自的 agent CLI。`agent-council` 不管理 OAuth、token、API key，也不保存憑證。

### 基本用法

```bash
agent-council ask "請 review 這個架構，列出前三個風險。"
agent-council ask "請 review 這個方案" --providers codex,gemini
agent-council continue "把剛剛的結論整理成實作步驟。"
agent-council chat
```

### 自訂 agents

在 `agents.yaml` 定義自己的 agents：

```yaml
agents:
  local-llama:
    command: ["ollama", "run", "llama3.1", "{prompt}"]
    role: "Role: Local reviewer. Be concise and call out uncertainty."
```

執行：

```bash
agent-council ask "請 review 這個方案" --config agents.yaml --providers local-llama
agent-council chat --config agents.yaml --providers local-llama
```

`{prompt}` 會被替換成完整的 council prompt。內建 agents 仍可使用，config 裡同名項目會覆蓋內建設定。

## 简体中文快速指南

`agent-council-cli` 是一个小型 CLI wrapper：把同一个 prompt 同时丢给你本机已登录的 Claude、Codex、Gemini、Ollama 或自定义 CLI，并列显示结果，同时保留可追溯的 JSONL audit log。

它不是 tmux / worktree / dashboard，也不是自动化 agent swarm。它只做一件事：帮你少复制粘贴几次，快速比较不同 AI CLI 的答案。

### 安装

```bash
git clone https://github.com/MakiDevelop/agent-council-cli.git
cd agent-council-cli
python -m pip install -e ".[dev]"
```

使用前请先在 terminal 里登录各自的 agent CLI。`agent-council` 不管理 OAuth、token、API key，也不保存凭证。

### 基本用法

```bash
agent-council ask "请 review 这个架构，列出前三个风险。"
agent-council ask "请 review 这个方案" --providers codex,gemini
agent-council continue "把刚才的结论整理成实现步骤。"
agent-council chat
```

### 自定义 agents

在 `agents.yaml` 定义自己的 agents：

```yaml
agents:
  local-llama:
    command: ["ollama", "run", "llama3.1", "{prompt}"]
    role: "Role: Local reviewer. Be concise and call out uncertainty."
```

执行：

```bash
agent-council ask "请 review 这个方案" --config agents.yaml --providers local-llama
agent-council chat --config agents.yaml --providers local-llama
```

`{prompt}` 会被替换成完整的 council prompt。内置 agents 仍可使用，config 里同名项目会覆盖内置设置。

## 日本語クイックガイド

`agent-council-cli` は小さな CLI wrapper です。同じ prompt を、すでにローカルで認証済みの Claude、Codex、Gemini、Ollama、または任意の CLI に並列で渡し、結果を比較しやすく表示し、追跡可能な JSONL audit log を残します。

tmux / worktree / dashboard ではなく、自律型 agent swarm でもありません。目的はシンプルです。同じ質問を何度もコピー＆ペーストせず、複数の AI CLI の回答をすばやく比較することです。

### インストール

```bash
git clone https://github.com/MakiDevelop/agent-council-cli.git
cd agent-council-cli
python -m pip install -e ".[dev]"
```

利用前に、それぞれの agent CLI へ terminal からログインしてください。`agent-council` は OAuth、token、API key、ブラウザログインを管理せず、認証情報も保存しません。

### 基本的な使い方

```bash
agent-council ask "このアーキテクチャを review して、上位3つのリスクを挙げてください。"
agent-council ask "この案を review してください" --providers codex,gemini
agent-council continue "先ほどの結論を具体的な実装手順にしてください。"
agent-council chat
```

### カスタム agents

`agents.yaml` で独自の agents を定義できます：

```yaml
agents:
  local-llama:
    command: ["ollama", "run", "llama3.1", "{prompt}"]
    role: "Role: Local reviewer. Be concise and call out uncertainty."
```

実行例：

```bash
agent-council ask "この案を review してください" --config agents.yaml --providers local-llama
agent-council chat --config agents.yaml --providers local-llama
```

`{prompt}` は完全な council prompt に置き換えられます。設定ファイルを指定しても built-in agents は利用でき、同名の設定は built-in を上書きします。

## License

MIT
