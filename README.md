# ai-flow-cli

> **Lightweight, fast terminal AI wrapper around modern coding harnesses with Rich markdown and math rendering.**

Wraps fast headless AI harnesses (`pi`, `omp`, `claude`, `codex`, `copilot`, `opencode`) for everyday queries and Unix pipelines.

![ai-flow-cli demo](assets/demo.gif)

---

## ⚡ Features

- 🚀 **Multi-Harness Support** — seamlessly autodetect and use `pi`, `omp`, `claude`, `codex`, `copilot`, or `opencode`.
- 🧙 **Interactive Setup Wizard** — run `ai --wizard` to inspect detected harnesses and choose your default.
- 🎨 **Rich Terminal Markdown & LaTeX** — renders clean markdown, tables, syntax highlighting, and math formulas in the terminal.
- 💬 **No Quotes Required** — run `ai what is the biggest object on earth` directly.
- 🚰 **Pure Unix Pipelines** — stdin context injection and clean raw text output when piped.
- 🛠️ **Tools On Demand** — pass `--tools` when agentic filesystem/system actions are needed.

---

## 📦 Installation

### 1. Arch Linux (AUR)
```bash
yay -S ai-flow-cli
# or paru:
paru -S ai-flow-cli
```

### 2. Recommended: Install via `mise`
```bash
mise use -g pipx:ai-flow-cli
# or via python backend:
mise use -g pip:ai-flow-cli
```

### 3. Install via PyPI (`pip` / `pipx` / `uv`)
```bash
# Standard pip install:
pip install --user ai-flow-cli

# Isolated global CLI with pipx:
pipx install ai-flow-cli

# Fast install with uv:
uv tool install ai-flow-cli
```

### 4. One-Line Script Install
```bash
curl -sSL https://raw.githubusercontent.com/Codder13/ai-flow-cli/main/install.sh | bash
```

---

## 🛠️ Usage

### 1. Initial Setup & Harness Selection Wizard
Run the interactive wizard to detect installed harnesses and set your preferred default:
```bash
ai --wizard
```
If no config exists yet, `ai` automatically prompts the wizard on first run when interactive, or picks the first detected harness (`pi` -> `omp` -> `claude` -> ...).

### 2. Direct Questions (Fast Headless Mode)
No quotes needed:
```bash
ai explain what is eBPF in 3 bullet points
```

### 3. Switching Agent Harnesses on the Fly
Use `-a` or `--agent` (or `--harness`) to override your default agent harness for a single query:
```bash
ai -a claude explain why rust ownership works this way
ai -a omp write a bash script to backup my dotfiles
```

### 4. Handoff to Harness TUI (`-H / --handoff`)
When a terminal query evolves into a deeper interactive agent session, hand off your entire conversation context to a full harness TUI:
```bash
# Handoff current context to default or specified harness TUI
ai -H
ai -H omp
ai -H claude "Fix all broken unit tests across the whole workspace"
```

### 5. Tool Execution (Default: Enabled) & Disabling Tools
By default, queries run with tool execution enabled so the AI can inspect files and run commands. Pass `--no-tools` (or `-nt`) to prevent the AI from accessing tools:
```bash
ai check git status and run tests
ai --no-tools "explain how quicksort works"
```
### 6. Unix Pipelines & Input Redirection
When piped, `ai` preserves standard Unix conventions:
```bash
git diff | ai explain these changes
cat error.log | ai "what caused this panic?"
curl -s https://example.com | ai summarize this page
```

Output is automatically raw and unformatted when redirected to a pipe or file:
```bash
ai "generate a python regex for uuid4" > regex.txt
```

---

## ⚙️ Configuration

Settings are stored in `~/.config/ai/config.json`:
```json
{
  "harness": "pi"
}
```

You can change it anytime via:
```bash
ai --wizard
```

---

## 📄 License

MIT
