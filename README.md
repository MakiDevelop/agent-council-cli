# agent-council-cli

Prompt-native multi-agent validation loop for Claude, Codex, and Gemini CLIs.

This is not an autonomous agent swarm. It is a small command-line harness for
asking multiple CLI agents the same question, comparing their answers, and
keeping an append-only audit trail.

> Authentication model: users log in to each agent CLI from their own terminal
> first. `agent-council-cli` does not manage OAuth, store API keys, or run
> browser login flows. It only calls local agent CLIs that are already
> authenticated on the user's machine.

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

## 繁體中文快速指南

`agent-council-cli` 是一個以 prompt 為中心的多代理驗證 CLI。它不是自動化 agent swarm，而是把同一個問題同時交給多個本機 agent CLI，例如 Claude、Codex、Gemini，並保留可追溯的 JSONL audit log。

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

`agent-council-cli` 是一个以 prompt 为中心的多代理验证 CLI。它不是自动化 agent swarm，而是把同一个问题同时交给多个本机 agent CLI，例如 Claude、Codex、Gemini，并保留可追溯的 JSONL audit log。

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

`agent-council-cli` は、prompt を中心にしたマルチエージェント検証用 CLI です。自律型の agent swarm ではなく、同じ質問を Claude、Codex、Gemini などのローカル agent CLI に並列で渡し、比較しやすい要約と追跡可能な JSONL audit log を残します。

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
