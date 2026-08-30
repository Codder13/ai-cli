# ai-cli

> **Sub-5ms streaming AI assistant & autonomous agent for Unix terminals with Rich markdown rendering and session memory.**

Compatible with any OpenAI-compatible provider: **Ollama, vLLM, LM Studio, Groq, OpenRouter, Together AI, OpenAI, and Antigravity / OMP**.

---

## ⚡ Why `ai-cli`?

Most AI command-line tools (`sgpt`, `llm`, `open-interpreter`) pull in dozens of heavy Python packages (`requests`, `pydantic`, `openai`, `click`), resulting in **200ms–400ms startup latency** before sending a single byte over the network.

`ai-cli` is engineered for speed, minimalism, and true Unix ergonomics:
- ⚡ **Instant Startup (< 5ms)** — starts and begins execution immediately.
- 🤖 **Autonomous Agent Mode (Default)** — equipped with 5 essential tools (`bash`, `read_file`, `write_file`, `search_web`, `fetch_web_page`).
- 🎨 **Rich Terminal Markdown** — syntax-highlighted code blocks, auto-aligned tables, blockquotes, and task checkboxes rendered cleanly in your terminal.
- 🧠 **Per-Terminal Session Memory** — preserves conversation context automatically within the same terminal tab/session (scoped by shell Process ID).
- 🌐 **Zero-Key Web Search** — live Google/Startpage + DuckDuckGo search integration without requiring third-party search API keys.
- 🚀 **Heavy Harness Handoff (`-H`)** — hand off active conversation context to `omp`, `claude`, `codex`, or `pi` when a task outgrows a lightweight CLI.
- 🚰 **Pure Unix Pipelines** — seamlessly handles `stdin`, trailing instructions, and outputs clean raw text when piped to files or other CLI tools.

---

## 📦 Installation

### 1. One-Line Install (Recommended)

```bash
curl -sSL https://raw.githubusercontent.com/Codder13/ai-cli/main/install.sh | bash
```

### 2. Manual / Git Clone

```bash
git clone https://github.com/Codder13/ai-cli.git ~/Projects/ai-cli
ln -sf ~/Projects/ai-cli/src/ai_cli/main.py ~/.local/bin/ai
```

### 3. Dependencies
Requires Python 3.8+ and `rich` for terminal markdown formatting:
```bash
pip install rich
# or on Arch Linux:
sudo pacman -S python-rich
```

---

## 🛠️ Usage

### 1. Direct Asking & Autonomous Tasks (Default)
`ai` runs in agent mode by default, choosing when to search the web, read files, or execute commands to give you an accurate, grounded answer:

```bash
# Autonomous research & web searching
ai search the latest zig release and summarize changes

# Local codebase inspection & execution
ai inspect package.json and run the build script

# General knowledge
ai what is the biggest crater on the moon
```

### 2. Pure No-Tools Streaming (`-n / --no-tools`)
If you want instant, direct token streaming without tool execution:

```bash
ai -n "explain quantum computing in 3 bullets"
```

### 3. Unix Pipelines & Stdin
Pipe terminal output directly into `ai` with or without trailing instructions:

```bash
# Summarize git changes
git diff | ai summarize these changes in 3 bullet points

# Explain log errors
cat /var/log/nginx/error.log | tail -n 20 | ai explain these errors

# Pipe output cleanly to file (automatically strips ANSI formatting)
ai -n generate a json array of 5 fruits > fruits.json
```

### 4. Terminal Session Memory (Automatic)
`ai` automatically preserves conversation history within the same terminal tab/session:

```bash
❯ ai what is the largest file in this project
# ... Inspects directory and lists the largest file ...

❯ ai how can I optimize it
# ... Automatically remembers the file from the previous turn!

# Clear conversation memory for the current tab:
❯ ai -C    # or ai --clear
```

### 5. Handoff to Heavy Harnesses (`-H / --handoff`)
When a simple task evolves into a large-scale refactor, codebase overhaul, or multi-file debugging session, hand off your entire conversation session context to a full workspace agent:

```bash
# Handoff conversation to Oh My Pi / Hermes (default):
❯ ai -H "Refactor all affected modules and run test suite"

# Handoff to Claude Code:
❯ ai -H claude "Fix all broken unit tests across the whole workspace"

# Supported harnesses: omp, claude, codex, pi
```

### 6. Interactive Tool Approvals (`-c / --confirm`)
By default, `ai` executes safe tools autonomously. If you prefer human-in-the-loop confirmation before each action:

```bash
ai -c "clean up temp and cache files in this directory"
```

---

## ⚙️ Configuration Cascade

`ai-cli` resolves configuration in the following order:
1. **CLI Flags**: `-m`, `-u`, `-k`, `-s`
2. **Environment Variables**: `AI_MODEL`, `AI_BASE_URL`, `AI_API_KEY`
3. **Config File**: `~/.config/ai/config.json`
4. **OMP / AGM Config**: `~/.omp/agent/models.yml` (auto-detected)

### Initialize a config template:
```bash
ai --init-config
```

This generates `~/.config/ai/config.json`:
```json
{
  "base_url": "https://api.openai.com/v1",
  "api_key": "your-api-key",
  "model": "gpt-4o-mini",
  "system_prompt": "You are a concise, helpful terminal assistant.",
  "temperature": 0.7,
  "require_approval": false
}
```

---

## 📖 CLI Reference

```text
usage: ai [-h] [-n] [-c] [-y] [-m MODEL] [-u BASE_URL] [-k API_KEY]
          [-s SYSTEM] [-t TEMPERATURE] [--max-turns MAX_TURNS] [--init-config]
          [-v] [-C] [-H [HARNESS]]
          [prompt ...]

positional arguments:
  prompt                User prompt or instruction

options:
  -h, --help            Show this help message and exit
  -n, --no-tools        Disable tools and run in fast direct streaming completion mode
  -c, --confirm         Require manual confirmation for each tool action
  -y, --yes             Bypass confirmation and auto-approve all tool actions
  -m, --model MODEL     Model identifier (default: gemini-3.7-flash-high or config)
  -u, --base-url BASE   OpenAI-compatible API base URL
  -k, --api-key KEY     API authorization key
  -s, --system SYSTEM   Custom system prompt
  -t, --temperature T   Sampling temperature (0.0 - 2.0)
  --max-turns N         Maximum tool execution turns in agent mode (default: 25)
  --init-config         Create a default config template at ~/.config/ai/config.json
  -v, --version         Show version
  -C, --clear           Clear conversation memory for the current terminal session
  -H, --handoff [NAME]  Handoff session context to a heavy agent harness (omp, claude, codex, pi; default: omp)
```

---

## 📄 License

[MIT](LICENSE)
