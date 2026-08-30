# ⚡ ai-cli

> **Zero-dependency, ultra-fast streaming AI CLI for Unix pipelines.**  
> Works with any OpenAI-compatible API (OpenAI, Groq, Ollama, vLLM, OpenRouter, Together AI).

```bash
$ ai what is the biggest thing on the moon
$ git diff | ai summarize these changes in 3 bullet points
```

---

## ✨ Why `ai-cli`?

Most terminal AI clients (`sgpt`, `llm`, `open-interpreter`) pull in dozens of heavy dependencies (`pydantic`, `rich`, `requests`, `openai`), resulting in **200ms–500ms of startup latency** before sending a single byte.

* **⚡ Sub-5ms startup latency** — Zero external dependencies. Uses 100% Python standard library (`urllib`, `json`, `argparse`).
* **🌊 Instant live streaming** — Streams response tokens to stdout in real-time.
* **🔌 Native Unix pipeline integration** — Cleanly accepts piped `stdin` combined with positional prompt instructions.
* **🛡️ Bulletproof & Maintenance-free** — No virtualenvs required, no site-packages breakages on rolling-release Python updates.
* **⚙️ Universal Compatibility** — Works with any OpenAI-compatible API endpoint.

---

## 🚀 Quick Install

### 1-Line Install (Recommended)
```bash
curl -sSL https://raw.githubusercontent.com/Codder13/ai-cli/main/install.sh | bash
```

### Or clone and link:
```bash
git clone https://github.com/Codder13/ai-cli.git ~/Projects/ai-cli
ln -sf ~/Projects/ai-cli/src/ai_cli/main.py ~/.local/bin/ai
```

---

## ⚙️ Configuration

`ai-cli` checks settings in the following order:
**CLI Flags** $\to$ **Environment Variables** $\to$ **`~/.config/ai/config.json`**.

### Environment Variables
Add to your `~/.bashrc` or `~/.zshrc`:

```bash
export AI_BASE_URL="https://api.openai.com/v1"  # Or your Ollama/vLLM/OpenRouter URL
export AI_API_KEY="sk-..."
export AI_MODEL="gpt-4o-mini"
```

### Or create a config file:
```bash
ai --init-config
```
This generates `~/.config/ai/config.json`:
```json
{
  "base_url": "https://api.openai.com/v1",
  "api_key": "sk-...",
  "model": "gpt-4o-mini",
  "system_prompt": "",
  "temperature": 0.7
}
```

---

## 💡 Usage Examples

### 1. Direct unquoted prompts
```bash
ai explain the difference between processes and threads
```

### 2. Piped Input + Instructions
```bash
# Summarize git changes
git diff | ai summarize these changes in 3 bullet points

# Debug error logs
cat /var/log/nginx/error.log | tail -n 20 | ai explain what is causing this 502

# Format JSON / code
curl -s https://api.sample.com/data | ai convert this to a clean TypeScript interface
```

### 3. CLI Overrides on the fly
```bash
# Switch models for a single prompt
ai -m claude-3-5-sonnet "write a regex for validating IPv6 addresses"

# Add a system persona / constraint
ai -s "You are a senior Linux kernel engineer. Answer concisely." what is eBPF
```

---

## 📄 License
[MIT](LICENSE)
