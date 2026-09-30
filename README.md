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
- 🛠️ **Tools On Demand** — tools are on by default; `--no-tools` for plain answers.
- 🐚 **`ai do`** — natural language → one shell command, confirm `[Y/e/n]` before it runs.
- 📝 **`ai commit`** — Conventional Commit message from your staged diff, matching your repo's style.
- 🩺 **`ai explain`** — `make 2>&1 | ai explain` tells you what broke and how to fix it.
- 📂 **`-f 'src/**/*.py'`** — attach files by glob as context.
- 📋 **`-c / --copy`** — copy the answer (or just its code block) to the clipboard.
- 🧭 **Per-directory context** — `.ai.md` in a project + `~/.config/ai/context.md`, injected automatically.
- 🔎 **`ai log`** — fuzzy-search past sessions with fzf and a live preview.
- 🧾 **`--json`** — machine-readable output for scripts.
- ⌨️ **zsh widget** — type what you want, press `Ctrl+G`, get the command.

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

### 7. Shell Commands: `ai do`
```bash
ai do find files over 100MB in my home
# $ find ~ -type f -size +100M -exec ls -lh {} +
# Run it? [Y/e/n]
```
`e` lets you edit the command before running; executed commands land in your shell history.
`ai do --print ...` only prints the command (great for scripts).

### 8. Commit Messages: `ai commit`
```bash
git add -p
ai commit            # shows the message → [Y]es commit / [e]dit in $EDITOR / [n]o
ai commit --print    # just print it
ai commit "mention the issue #12"
```

### 9. Explain Errors: `ai explain`
```bash
cargo build 2>&1 | ai explain
journalctl -u nginx -n 50 | ai explain "why won't it start?"
```

### 10. Files as Context: `-f / --file`
```bash
ai -f 'src/**/*.luau' "where is player data saved?"
ai -f README.md -f pyproject.toml "is the install section accurate?"
```
Binary files are skipped; each file is capped at 200 KB (1 MB total).

### 11. Clipboard, JSON & Footer
```bash
ai -c "regex for an ipv4 address"         # copies the code block (wl-copy/xclip/pbcopy)
ai --json "capital of France" | jq -r .response
```
A dim `harness · model · 3.2s` footer is shown on terminals. Hide it with `AI_NO_FOOTER=1`.

### 12. Session History: `ai log`
```bash
ai log              # fzf picker with preview (plain list without fzf)
ai log rojo         # only sessions mentioning "rojo"
ai log -a --json    # everything, as JSON
```

### 13. zsh Widget
```bash
# ~/.zshrc
eval "$(ai --zsh)"
```
Type `undo last git commit but keep changes`, press **Ctrl+G** → the line becomes
`git reset --soft HEAD~1`. Review, then Enter. Change the key with `AI_ZSH_KEY`.

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

### Context files
Anything in these files is prepended to every prompt (skip with `--no-context`):

| File | Scope |
|---|---|
| `~/.config/ai/context.md` | Always: who you are, your OS, preferences |
| `.ai.md` (nearest, walking up from cwd, stops at `$HOME`) | Per project: conventions, stack, commands |

---

## 📄 License

MIT
