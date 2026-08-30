# ai-cli

> **Zero-dependency, sub-5ms streaming AI CLI & autonomous agent for Unix terminals and pipelines.**

Compatible with any OpenAI-compatible provider: **Ollama, vLLM, LM Studio, Groq, OpenRouter, Together AI, OpenAI, and AGM / OMP**.

---

## Why `ai-cli`?

Most AI command-line tools (`sgpt`, `llm`, `open-interpreter`) pull in dozens of heavy Python packages (`requests`, `pydantic`, `rich`, `openai`), resulting in **200ms–400ms startup latency** before sending a single byte over the network.

`ai-cli` is written in **100% pure Python standard library**:
- ⚡ **Sub-5ms startup latency** — starts and begins streaming instantly.
- 🪶 **Zero dependencies** — no `pip` virtual environment breaks, no C-extension issues.
- 🚰 **Pure Unix pipeline design** — seamlessly handles `stdin`, arguments, and pipes clean text for `grep`, `sed`, or redirection.
- 🤖 **Pragmatic Agent Mode (`-a`)** — equipped with 4 essential tools (`bash`, `read_file`, `write_file`, `web_search`) with human-in-the-loop approvals.
- 🌐 **Built-in DuckDuckGo Web Search** — live web research without needing API keys.

---

## Installation

### 1. One-Line Install (Recommended)

```bash
curl -sSL https://raw.githubusercontent.com/Codder13/ai-cli/main/install.sh | bash
```

### 2. Manual / Git Clone

```bash
git clone https://github.com/Codder13/ai-cli.git
ln -sf $(pwd)/ai-cli/src/ai_cli/main.py ~/.local/bin/ai
```

---

## Usage

### 1. Instant Streaming Prompt
```bash
ai what is the biggest thing on the moon
```

### 2. Unix Pipelines & Stdin
```bash
# Summarize git changes
git diff | ai summarize these changes in 3 bullet points

# Explain log errors
cat /var/log/nginx/error.log | tail -n 20 | ai explain these errors

# Pipe output cleanly to file
ai generate a json array of 5 fruits > fruits.json
```

### 3. Agent Mode (Default)
By default, `ai` runs as an autonomous agent equipped with 5 essential tools (`bash`, `read_file`, `write_file`, `search_web`, `fetch_web_page`) to solve tasks and research questions.

```bash
# Autonomous research & web searching
ai who is denis bolba

# Inspect local code & run commands
ai inspect this git repository and list the top 3 largest python functions

# Require manual confirmation before each tool action (-c)
ai -c "remove all temp and cache files in the current folder"
```

### 4. Pure No-Tools Completion (`-n / --no-tools`)
If you want direct token streaming without tool execution:
```bash
ai -n "explain quantum computing in 3 bullets"
```
---

## Configuration Cascade

`ai-cli` looks for credentials in the following order:
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

## CLI Options

```text
usage: ai [-h] [-a] [-c] [-y] [-m MODEL] [-u BASE_URL] [-k API_KEY] [-s SYSTEM]
          [-t TEMPERATURE] [--init-config] [-v]
          [prompt ...]

options:
  prompt                User prompt or instruction
  -a, --agent           Enable autonomous agent mode with tools (bash, read_file, write_file, web_search)
  -c, --confirm         Require manual confirmation for each tool action
  -y, --yes             Bypass confirmation and auto-approve all tool actions
  -m, --model MODEL     Model identifier (default: gemini-3.7-flash-high)
  -u, --base-url BASE   OpenAI-compatible API base URL
  -k, --api-key KEY     API authorization key
  -s, --system SYSTEM   Custom system prompt
  -t, --temperature T   Sampling temperature (0.0 - 2.0)
  --init-config         Create default config template at ~/.config/ai/config.json
  -v, --version         Show version
```

---

## License

[MIT](LICENSE)
