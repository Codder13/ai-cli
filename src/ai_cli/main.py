#!/usr/bin/env python3
"""ai-cli: Fast CLI wrapper around local AI harnesses for everyday queries and Unix pipelines."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

# Rich is imported lazily (see _make_console) so `ai --help`, `--raw` and
# piped output don't pay ~250 ms of import time for markdown rendering.
try:
    import rich  # noqa: F401  (cheap: only the package __init__)

    HAS_RICH = True
except ImportError:
    HAS_RICH = False

try:
    from ai_cli.latex_render import (
        render_mixed_markdown_with_math,
        sanitize_inline_math,
    )
except ImportError:
    # Resolve symlink to real path of main.py, then add parent of ai_cli (src) to sys.path
    real_script = os.path.realpath(__file__)
    src_dir = os.path.dirname(os.path.dirname(real_script))
    if src_dir not in sys.path:
        sys.path.insert(0, src_dir)
    from ai_cli.latex_render import (
        render_mixed_markdown_with_math,
        sanitize_inline_math,
    )

CONFIG_DIR = Path.home() / ".config" / "ai"
CONFIG_FILE = CONFIG_DIR / "config.json"
CACHE_DIR = Path.home() / ".cache" / "ai" / "sessions"
FX_HOME = Path.home() / ".fx"
# fx keeps its own session store; we only remember the session id per terminal.
FX_SESSION_FILE = "session_id"

# Order used when no harness is configured: first one found in PATH wins.
HARNESS_PREFERENCE = ("pi", "omp", "claude", "codex", "copilot", "opencode", "fx")

LATEX_SYSTEM_PROMPT = (
    "Formatting instructions: For mathematical equations, display formulas, or matrices, "
    "use standard LaTeX block math ($$ ... $$ or \\[ ... \\]). For plain physical units, "
    "numbers, and measurements in text, write normal readable text without math dollar signs "
    "(e.g. ~21,196 km, 65.5 million tons, 200 km²)."
)


def get_terminal_session_key() -> str:
    """Get unique key identifying current terminal session / tab."""
    # 1. Multiplexer or terminal window variables
    for var in ("KITTY_WINDOW_ID", "WEZTERM_PANE", "TMUX_PANE", "HERDR_PANE_ID", "WINDOWID"):
        val = os.environ.get(var)
        if val:
            safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in val)
            return f"{var.lower()}_{safe}"

    # 2. Parent tty from proc
    ppid = os.getppid()
    for fd in (0, 1, 2):
        try:
            target = os.readlink(f"/proc/{ppid}/fd/{fd}")
            if target.startswith("/dev/"):
                safe = target[5:].replace("/", "_")
                return f"tty_{safe}"
        except OSError:
            pass

    # 3. Process sid or ppid fallback
    try:
        return f"sid_{os.getsid(ppid)}"
    except OSError:
        return f"ppid_{ppid}"


def get_terminal_session_dir(harness_name: str) -> str:
    """Return directory where session files for current terminal tab are kept."""
    key = get_terminal_session_key()
    session_dir = str(CACHE_DIR / harness_name / key)
    os.makedirs(session_dir, exist_ok=True)
    return session_dir


def clear_terminal_session() -> None:
    """Clear session history for current terminal tab across all harnesses."""
    key = get_terminal_session_key()
    if CACHE_DIR.is_dir():
        for harness_dir in CACHE_DIR.iterdir():
            if harness_dir.is_dir():
                target = harness_dir / key
                if target.is_dir():
                    shutil.rmtree(target, ignore_errors=True)


def has_existing_session(session_dir: str) -> bool:
    """Check if session directory contains any saved session files."""
    try:
        return any(not e.startswith(".") for e in os.listdir(session_dir))
    except OSError:
        return False


def _prepare_session_dir(harness_name: str, session_mode: str) -> tuple[str, bool]:
    """Return (session_dir, resume) for harnesses that take --session-dir.

    ``session_mode == "new"`` wipes the directory first; ``resume`` is True
    only in ``auto`` mode when a previous session exists.
    """
    session_dir = get_terminal_session_dir(harness_name)
    if session_mode == "new":
        shutil.rmtree(session_dir, ignore_errors=True)
        os.makedirs(session_dir, exist_ok=True)
        return session_dir, False
    return session_dir, session_mode == "auto" and has_existing_session(session_dir)


def _extract_text_from_content(content: Any) -> str:
    """Extract plain text from message content block (string, list of dicts, etc.)."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict):
                if item.get("type") == "text" or item.get("text"):
                    parts.append(item.get("text", ""))
            elif isinstance(item, str):
                parts.append(item)
        return "\n".join(parts)
    return str(content) if content else ""


def load_terminal_session_history() -> list[dict[str, str]]:
    """Find and load conversation turns for the current terminal tab/pane across known harnesses."""
    key = get_terminal_session_key()
    session_files: list[Path] = []

    # First check current session key in all harness session directories
    if CACHE_DIR.is_dir():
        for harness_dir in CACHE_DIR.iterdir():
            if harness_dir.is_dir():
                target = harness_dir / key
                if target.is_dir():
                    session_files.extend(target.glob("*.jsonl"))
                    session_files.extend(target.glob(FX_SESSION_FILE))

    # Fallback: if no session files found for this tab, check most recent session file anywhere in CACHE_DIR
    if not session_files and CACHE_DIR.is_dir():
        session_files = [*CACHE_DIR.glob("*/*/*.jsonl"), *CACHE_DIR.glob(f"*/*/{FX_SESSION_FILE}")]

    if not session_files:
        return []

    # Pick the most recently modified session file
    latest_file = max(session_files, key=lambda p: p.stat().st_mtime)
    if latest_file.name == FX_SESSION_FILE:
        return _load_fx_history(latest_file)

    messages: list[dict[str, str]] = []
    try:
        with open(latest_file, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(data, dict) and data.get("type") == "message":
                    msg = data.get("message", {})
                    role = msg.get("role")
                    if role in ("user", "assistant"):
                        text = _extract_text_from_content(msg.get("content"))
                        if text and text.strip():
                            messages.append({"role": role, "content": text.strip()})
    except OSError:
        pass

    return messages


def _load_fx_history(session_id_file: Path) -> list[dict[str, str]]:
    """Load conversation turns from the fx session referenced by a stored session id."""
    try:
        session_id = session_id_file.read_text(encoding="utf-8").strip()
    except OSError:
        return []
    if not session_id:
        return []
    messages: list[dict[str, str]] = []
    try:
        with open(FX_HOME / "sessions" / session_id / "events.jsonl", encoding="utf-8") as f:
            for line in f:
                try:
                    event = json.loads(line).get("event", {})
                except (json.JSONDecodeError, AttributeError):
                    continue
                for role in ("user", "assistant"):
                    entry = event.get(role) if isinstance(event, dict) else None
                    if not isinstance(entry, dict):
                        continue
                    text = str(entry.get("text") or "")
                    # Strip the formatting/tool preamble we prepend to fx prompts
                    if role == "user" and LATEX_SYSTEM_PROMPT in text:
                        text = text.split(LATEX_SYSTEM_PROMPT, 1)[1]
                    if text.strip():
                        messages.append({"role": role, "content": text.strip()})
    except OSError:
        pass
    return messages


def format_session_for_handoff() -> str:
    """Format the current terminal session into a readable transcript for handoff."""
    history = load_terminal_session_history()
    if not history:
        return ""

    transcript = ["## Prior Conversation Context from `ai` session:\n"]
    for msg in history:
        role_label = "User" if msg["role"] == "user" else "Assistant"
        transcript.append(f"### {role_label}:\n{msg['content']}\n")
    return "\n".join(transcript)


# Harnesses whose TUI does not accept an initial prompt as a positional arg.
HANDOFF_NO_PROMPT = frozenset({"copilot"})


def execute_handoff(target_harness: str | None = None, extra_instruction: str = "") -> None:
    """Handoff the current session context to an interactive harness TUI."""
    if not target_harness:
        target_harness = resolve_harness(None)

    if not shutil.which(target_harness):
        sys.stderr.write(f"Error: Target harness '{target_harness}' executable not found in PATH.\n")
        sys.exit(1)

    context = format_session_for_handoff()
    initial_prompt = ""
    if context:
        initial_prompt = f"{context}\n## Next Goal / Instruction:\n"
        if extra_instruction:
            initial_prompt += extra_instruction
        else:
            initial_prompt += "Continue assisting the user based on the conversation history above."
    elif extra_instruction:
        initial_prompt = extra_instruction

    # Build interactive command to launch the harness TUI
    if target_harness == "fx":
        cmd = build_fx_handoff_cmd(initial_prompt)
    else:
        cmd = [target_harness]
        if initial_prompt and target_harness not in HANDOFF_NO_PROMPT:
            cmd.append(initial_prompt)

    try:
        os.execvp(cmd[0], cmd)
    except OSError as e:
        sys.stderr.write(f"Failed to handoff to {target_harness}: {e}\n")
        sys.exit(1)

def _session_dir_args(harness_name: str, session_mode: str) -> list[str]:
    """Session flags shared by pi and omp (per-terminal --session-dir)."""
    if session_mode == "none":
        return ["--no-session"]
    session_dir, resume = _prepare_session_dir(harness_name, session_mode)
    args = ["--session-dir", session_dir]
    if resume:
        args.append("-c")
    return args


def build_pi_cmd(
    model: str | None,
    enable_tools: bool = True,
    prompt: str = "",
    session_mode: str = "auto",
) -> list[str]:
    cmd = ["pi", "-p", *_session_dir_args("pi", session_mode)]

    if not enable_tools:
        cmd.append("--no-tools")
    cmd.extend(["--append-system-prompt", LATEX_SYSTEM_PROMPT])
    if model:
        cmd.extend(["--model", model])
    cmd.append(prompt)
    return cmd


def build_omp_cmd(
    model: str | None,
    enable_tools: bool = True,
    prompt: str = "",
    session_mode: str = "auto",
) -> list[str]:
    cmd = ["omp", "-p", *_session_dir_args("omp", session_mode)]

    if not enable_tools:
        cmd.append("--no-tools")
    else:
        cmd.append("--auto-approve")
    cmd.extend(["--append-system-prompt", LATEX_SYSTEM_PROMPT])
    if model:
        cmd.extend(["--model", model])
    cmd.append(prompt)
    return cmd


def build_claude_cmd(
    model: str | None,
    enable_tools: bool = True,
    prompt: str = "",
    session_mode: str = "auto",
) -> list[str]:
    cmd = ["claude", "-p"]
    if session_mode == "none":
        cmd.append("--no-session-persistence")
    elif session_mode == "auto":
        cmd.append("-c")

    if not enable_tools:
        cmd.extend(["--tools", ""])
    else:
        cmd.append("--dangerously-skip-permissions")
    cmd.extend(["--append-system-prompt", LATEX_SYSTEM_PROMPT])
    if model:
        cmd.extend(["--model", model])
    cmd.append(prompt)
    return cmd


def build_codex_cmd(
    model: str | None,
    enable_tools: bool = True,
    prompt: str = "",
    session_mode: str = "auto",
) -> list[str]:
    cmd = ["codex", "exec"]
    if session_mode == "none":
        cmd.append("--ephemeral")

    if not enable_tools:
        cmd.extend(["--sandbox", "read-only"])
    else:
        cmd.append("--dangerously-bypass-approvals-and-sandbox")
    if model:
        cmd.extend(["-m", model])
    cmd.append(f"{LATEX_SYSTEM_PROMPT}\n\n{prompt}")
    return cmd


def build_copilot_cmd(
    model: str | None,
    enable_tools: bool = True,
    prompt: str = "",
    session_mode: str = "auto",
) -> list[str]:
    cmd = ["copilot", "-p", f"{LATEX_SYSTEM_PROMPT}\n\n{prompt}", "--silent"]
    if session_mode == "auto":
        cmd.append("--continue")
    if enable_tools:
        cmd.append("--allow-all")
    else:
        cmd.extend(["--available-tools", ""])
    if model:
        cmd.extend(["--model", model])
    return cmd

def build_opencode_cmd(
    model: str | None,
    enable_tools: bool = True,
    prompt: str = "",
    session_mode: str = "auto",
) -> list[str]:
    cmd = ["opencode", "run"]
    if session_mode == "auto":
        cmd.append("-c")
    if enable_tools:
        cmd.append("--auto")
    if model:
        cmd.extend(["-m", model])
    cmd.append(f"{LATEX_SYSTEM_PROMPT}\n\n{prompt}")
    return cmd


FX_NO_TOOLS_PROMPT = (
    "Tool instructions: Do not call any tools. Answer directly from your own knowledge "
    "and the provided context."
)


def _fx_session_file() -> str:
    return os.path.join(get_terminal_session_dir("fx"), FX_SESSION_FILE)


def load_fx_session_id() -> str | None:
    """Return the fx session id remembered for the current terminal tab, if any."""
    try:
        with open(_fx_session_file(), encoding="utf-8") as f:
            return f.read().strip() or None
    except OSError:
        return None


def save_fx_session_id(session_id: str) -> None:
    try:
        with open(_fx_session_file(), "w", encoding="utf-8") as f:
            f.write(session_id)
    except OSError:
        pass


def build_fx_cmd(
    model: str | None,
    enable_tools: bool = True,
    prompt: str = "",
    session_mode: str = "auto",
) -> list[str]:
    # fx has no --session-dir: remember its session id per terminal tab and
    # resume with --resume-id. --json lets parse_fx_output capture the id.
    cmd = ["fx", "ask", "--json"]
    if session_mode == "none":
        cmd.append("--no-save")
    elif session_mode == "new":
        _prepare_session_dir("fx", "new")
    else:  # auto
        session_id = load_fx_session_id()
        if session_id:
            cmd.extend(["--resume-id", session_id])

    preamble = LATEX_SYSTEM_PROMPT
    if enable_tools:
        cmd.append("--full-access")
    else:
        # fx has no flag to disable tools; fall back to instructing the model
        preamble = f"{FX_NO_TOOLS_PROMPT}\n{preamble}"
    if model:
        cmd.extend(["--model", model])
    # --system would replace fx's whole base prompt, so prepend instead.
    cmd.extend(["--", f"{preamble}\n\n{prompt}"])
    return cmd


def parse_fx_output(stdout: str, session_mode: str = "auto") -> str:
    """Extract the final answer from `fx ask --json` and remember the session id."""
    try:
        data = json.loads(stdout.strip().splitlines()[-1])
    except (json.JSONDecodeError, IndexError):
        return stdout
    if not isinstance(data, dict):
        return stdout
    session_id = data.get("session_id")
    if session_id and session_mode != "none":
        save_fx_session_id(str(session_id))
    return str(data.get("final_output") or data.get("output") or "")


def build_fx_handoff_cmd(initial_prompt: str = "") -> list[str]:
    """fx's TUI takes no initial prompt: seed a saved session via `fx ask`, then resume it."""
    session_id = load_fx_session_id()
    if initial_prompt:
        seed_cmd = ["fx", "ask", "--json"]
        if session_id:
            seed_cmd.extend(["--resume-id", session_id])
        seed_cmd.extend(["--", initial_prompt])
        sys.stderr.write("Seeding fx session with conversation context...\n")
        try:
            proc = subprocess.run(seed_cmd, capture_output=True, stdin=subprocess.DEVNULL, text=True)
            if proc.returncode == 0:
                parse_fx_output(proc.stdout)
                session_id = load_fx_session_id() or session_id
            elif proc.stderr:
                sys.stderr.write(proc.stderr)
        except OSError as e:
            sys.stderr.write(f"Warning: could not seed fx session: {e}\n")
    return ["fx", "--resume", session_id] if session_id else ["fx"]


HARNESS_REGISTRY: dict[str, dict[str, Any]] = {
    "pi": {
        "name": "pi",
        "description": "Pi coding assistant (fast, headless mode)",
        "builder": build_pi_cmd,
    },
    "omp": {
        "name": "omp",
        "description": "Oh My Pi / Hermes (autonomous agent harness)",
        "builder": build_omp_cmd,
    },
    "claude": {
        "name": "claude",
        "description": "Claude Code CLI",
        "builder": build_claude_cmd,
    },
    "codex": {
        "name": "codex",
        "description": "OpenAI Codex CLI",
        "builder": build_codex_cmd,
    },
    "copilot": {
        "name": "copilot",
        "description": "GitHub Copilot CLI",
        "builder": build_copilot_cmd,
    },
    "opencode": {
        "name": "opencode",
        "description": "OpenCode CLI assistant",
        "builder": build_opencode_cmd,
    },
    "fx": {
        "name": "fx",
        "description": "fx native coding agent (fx.sh)",
        "builder": build_fx_cmd,
        "output_parser": parse_fx_output,
    },
}


def load_config() -> dict[str, Any]:
    """Load configuration from ~/.config/ai/config.json."""
    try:
        with open(CONFIG_FILE, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def save_config(config: dict[str, Any]) -> None:
    """Save configuration to ~/.config/ai/config.json."""
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)
            f.write("\n")
    except OSError as e:
        sys.stderr.write(f"Warning: Could not save configuration to {CONFIG_FILE}: {e}\n")


def detect_installed_harnesses() -> list[str]:
    """Return list of harness keys present in PATH."""
    return [key for key in HARNESS_REGISTRY if shutil.which(key)]


def _make_console() -> Any | None:
    """Create a Rich console on demand (keeps rich out of the startup path)."""
    if not HAS_RICH:
        return None
    from rich.console import Console

    return Console()


def run_harness_wizard(console: Any | None = None, current_harness: str | None = None) -> str:
    """Interactive wizard to select and save a default harness."""
    installed = detect_installed_harnesses()
    all_keys = list(HARNESS_REGISTRY.keys())
    use_rich = console is not None and HAS_RICH

    if use_rich:
        from rich.table import Table

        table = Table(title="Select AI Harness", show_header=True, header_style="bold cyan")
        table.add_column("#", style="dim", width=4)
        table.add_column("Harness", style="bold")
        table.add_column("Status", width=14)
        table.add_column("Description")

        for idx, key in enumerate(all_keys, 1):
            info = HARNESS_REGISTRY[key]
            status_str = "[green]✓ Installed[/green]" if key in installed else "[red]✗ Not found[/red]"
            active_marker = " [bold yellow](current)[/bold yellow]" if key == current_harness else ""
            table.add_row(str(idx), f"{key}{active_marker}", status_str, info["description"])

        console.print()
        console.print(table)
        console.print()
    else:
        print("\nSelect AI Harness:")
        for idx, key in enumerate(all_keys, 1):
            info = HARNESS_REGISTRY[key]
            status = "Installed" if key in installed else "Not found"
            marker = " (current)" if key == current_harness else ""
            print(f"  [{idx}] {key}{marker} [{status}] - {info['description']}")
        print()

    # Determine default choice
    default_idx = "1"
    if current_harness in all_keys:
        default_idx = str(all_keys.index(current_harness) + 1)
    elif installed:
        default_idx = str(all_keys.index(installed[0]) + 1)

    choices = [str(i) for i in range(1, len(all_keys) + 1)] + all_keys

    while True:
        try:
            if use_rich:
                from rich.prompt import Prompt

                ans = Prompt.ask(
                    "[bold cyan]Choose harness number or name[/bold cyan]",
                    choices=choices,
                    default=default_idx,
                )
            else:
                ans = input(f"Choose harness number or name [{default_idx}]: ").strip() or default_idx
        except (EOFError, KeyboardInterrupt):
            sys.stderr.write("\nAborted.\n")
            sys.exit(130)

        chosen = None
        if ans.isdigit():
            idx = int(ans) - 1
            if 0 <= idx < len(all_keys):
                chosen = all_keys[idx]
        elif ans in all_keys:
            chosen = ans

        if not chosen:
            continue

        if chosen not in installed:
            _print_msg(console, f"Warning: '{chosen}' binary was not found in PATH.", "yellow")
        cfg = load_config()
        cfg["harness"] = chosen
        save_config(cfg)
        _print_msg(console, f"✓ Saved default harness '{chosen}' to {CONFIG_FILE}\n", "green")
        return chosen


def _print_msg(console: Any | None, msg: str, style: str) -> None:
    if console is not None and HAS_RICH:
        console.print(f"[{style}]{msg}[/{style}]", highlight=False)
    else:
        print(msg)


def resolve_harness(cli_harness: str | None, console: Any | None = None) -> str:
    """Resolve which harness to use from CLI flag, env, config, or wizard."""
    supported = ", ".join(HARNESS_REGISTRY)
    if cli_harness:
        if cli_harness in HARNESS_REGISTRY:
            return cli_harness
        sys.stderr.write(f"Error: Unknown harness '{cli_harness}'. Supported: {supported}\n")
        sys.exit(1)

    # 1. Environment variable
    env_harness = os.environ.get("AI_HARNESS")
    if env_harness:
        if env_harness in HARNESS_REGISTRY:
            return env_harness
        sys.stderr.write(f"Warning: ignoring unknown AI_HARNESS='{env_harness}'. Supported: {supported}\n")

    # 2. Config file
    configured_harness = load_config().get("harness")
    if configured_harness in HARNESS_REGISTRY:
        return configured_harness

    # 3. Fallback: first installed harness from the preference list
    for name in HARNESS_PREFERENCE:
        if shutil.which(name):
            return name

    # 4. Nothing installed/configured: ask via wizard if interactive
    if sys.stdin.isatty():
        return run_harness_wizard(console=console or _make_console())

    # Last resort; main() reports a helpful "not installed" error.
    return HARNESS_PREFERENCE[0]


def _harness_missing_error(harness_name: str) -> None:
    """Explain that the harness is not installed and exit."""
    sys.stderr.write(f"Error: Harness '{harness_name}' executable not found in PATH.\n")
    installed = detect_installed_harnesses()
    if installed:
        sys.stderr.write(
            f"Installed harnesses: {', '.join(installed)}. "
            f"Use 'ai -a <name> ...' or run 'ai --wizard' to switch.\n"
        )
    else:
        sys.stderr.write(
            f"No supported harness found. Install one of: {', '.join(HARNESS_PREFERENCE)}\n"
        )
    sys.exit(1)


def _style(text: str, code: str) -> str:
    return f"\x1b[{code}m{text}\x1b[0m" if sys.stdout.isatty() and not os.environ.get("NO_COLOR") else text


def _render_help(text: str) -> str:
    """Bold section headers, dim comments — only on a terminal."""
    out = []
    for line in text.splitlines():
        if line and not line.startswith(" ") and line.endswith(":"):
            out.append(_style(line, "1;36"))
        elif line.lstrip().startswith("# "):
            out.append(_style(line, "90"))
        elif line.startswith("  $ "):
            out.append("  " + _style("$", "90") + line[3:])
        else:
            out.append(line)
    return "\n".join(out)


SUBCOMMAND_HELP: dict[str, str] = {
    "do": """ai do — describe what you want, get ONE shell command, confirm before it runs

Usage:
  ai do [options] <request>

Options:
  --print                Only print the command (no prompt, nothing runs) — for scripts
  -c, --copy             Also copy the command to the clipboard
  --json                 {"command", "harness", "seconds"}
  -a, -m                 Harness / model override

After the command is shown:
  Y / Enter              Run it (and add it to your shell history)
  e                      Edit it in place first, then run
  n                      Cancel

Examples:
  $ ai do find files over 100MB in my home
  # → find ~ -type f -size +100M -exec ls -lh {} +     Run it? [Y/e/n]
  $ ai do kill whatever is listening on port 3000
  $ ai do convert all .webp in this folder to png
  $ ai do --print show disk usage sorted | sh      # scripting
  # Tip: `ai do you know …` is treated as a normal question, not a command.
""",
    "commit": """ai commit — Conventional Commit message from your staged diff

Usage:
  ai commit [options] [extra instruction]

Options:
  --print                Only print the message (don't commit)
  -a, -m                 Harness / model override

Then:
  Y / Enter              git commit -m "<message>"
  e                      Open the message in $EDITOR (git commit -e)
  n                      Cancel

Examples:
  $ git add -p && ai commit
  $ ai commit "mention it fixes #12"
  $ ai commit --print | wl-copy
  # It reads your last 10 commit subjects to match the repo's style.
""",
    "explain": """ai explain — pipe output or an error in, get what broke and how to fix it

Usage:
  <command> 2>&1 | ai explain [question]
  ai explain -f <file> [question]

Examples:
  $ cargo build 2>&1 | ai explain
  $ journalctl -u nginx -n 50 | ai explain "why won't it start?"
  $ ai explain -f crash.log
  # Don't forget 2>&1 — most errors go to stderr.
""",
    "log": """ai log — browse and search your past `ai` sessions

Usage:
  ai log [query]
  ai log -a [query]        Print every match instead of opening fzf
  ai log --json [query]

Examples:
  $ ai log                 # fzf picker, transcript preview on the right
  $ ai log rojo            # only sessions mentioning "rojo"
  $ ai log -a docker       # plain list, e.g. to grep
  $ ai log --json | jq '.[0]'
  # Without fzf installed it prints a plain list.
""",
}


def print_help(topic: str | None = None) -> None:
    if topic in SUBCOMMAND_HELP:
        print(_render_help(SUBCOMMAND_HELP[topic]))
        return
    supported = ", ".join(HARNESS_REGISTRY.keys())
    help_text = f"""ai — fast terminal AI for questions, pipelines & code

Usage:
  ai [options] <question>
  <command> | ai [options] [question]
  ai <do|commit|explain|log> …        (ai <command> --help for details)

Ask:
  $ ai how do I extract a .tar.gz file     # no quotes needed
  $ ai "what was the command you just suggested?"   # same tab = same conversation
  $ ai --new "different topic"                        # fresh conversation

Pipes:
  $ cat main.py | ai explain what this does
  $ git diff | ai review these changes
  $ ai "regex for uuid4" > regex.txt       # piped output is plain text

Commands:
  ai do <request>        Natural language → one shell command, confirm [Y/e/n] before running
    $ ai do find files over 100MB in my home
  ai commit              Commit message from the staged diff → confirm → git commit
    $ git add -p && ai commit
  ai explain             Explain piped errors/output and how to fix them
    $ cargo build 2>&1 | ai explain
  ai log [query]         Search past sessions (fzf + preview)
    $ ai log rojo

Files & context:
  -f, --file <glob>      Attach files (repeatable; quote globs)
    $ ai -f 'src/**/*.luau' "where is player data saved?"
    $ ai -f README.md -f pyproject.toml "is the install section right?"
  --no-context           Skip ~/.config/ai/context.md and the nearest .ai.md
    # Put your stack/preferences in ~/.config/ai/context.md and project rules in
    # <project>/.ai.md — they're added to every prompt automatically.

Output:
  -c, --copy             Copy the answer (just the code block if there is one)
    $ ai -c "bash one-liner to count lines in all .py files"
  --json                 {{"response", "code", "harness", "model", "seconds"}}
    $ ai --json "capital of France" | jq -r .response
  --raw                  Plain text, no markdown rendering

Harness & model:
  -a, --agent <name>     {supported}
    $ ai -a claude "optimize this query" < query.sql
  -m, --model <name>     Model override
  -H, --handoff [name]   Continue this conversation in the harness TUI
    $ ai -H omp "now implement it"
  --wizard               Pick and save your default harness

Session & tools:
  --new                  Start a new conversation in this terminal
  --no-session           One-off question, nothing saved
  --clear                Forget this terminal's conversation
  -nt, --no-tools        No tool access (plain answer)
  -t, --tools            Tools on (default)

Shell:
  --zsh                  Print the zsh widget: type a request, press Ctrl+G → command
    $ echo 'eval "$(ai --zsh)"' >> ~/.zshrc

Other:
  -V, --version          Version
  -h, --help             This help;  ai <command> --help for command help
  --                     Everything after is prompt text:  ai -- --why-is-this-flag

Environment:
  AI_HARNESS             Default harness (overrides ~/.config/ai/config.json)
  AI_NO_FOOTER=1         Hide the dim "harness · model · 3.2s" footer
  AI_ZSH_KEY             Key for the zsh widget (default ^G)
  NO_COLOR=1             No colors in help
"""
    print(_render_help(help_text))


def _run_harness(cmd: list[str]) -> tuple[str, str]:
    """Run the harness, returning (stdout, stderr). Exits on failure."""
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.DEVNULL,
            text=True,
        )
        stdout_data, stderr_data = proc.communicate()
    except FileNotFoundError:
        _harness_missing_error(cmd[0])
    except KeyboardInterrupt:
        sys.exit(130)

    if proc.returncode != 0:
        if stderr_data:
            sys.stderr.write(stderr_data)
        sys.exit(proc.returncode)
    return stdout_data, stderr_data


def _do_question_words() -> frozenset[str]:
    from ai_cli.extras import DO_QUESTION_WORDS

    return DO_QUESTION_WORDS


SUBCOMMANDS = frozenset({"do", "commit", "explain", "log"})


class Options:
    """Parsed command-line options."""

    def __init__(self) -> None:
        self.raw = False
        self.enable_tools = True
        self.session_mode = "auto"
        self.model: str | None = None
        self.harness: str | None = None
        self.handoff = False
        self.handoff_harness: str | None = None
        self.copy = False
        self.json = False
        self.use_context = True
        self.files: list[str] = []
        self.print_only = False  # `ai do --print`
        self.all_matches = False  # `ai log -a`
        self.words: list[str] = []

    @property
    def prompt(self) -> str:
        return " ".join(self.words).strip()


def parse_args(args: list[str]) -> Options:
    o = Options()
    i = 0
    while i < len(args):
        arg = args[i]
        nxt = args[i + 1] if i + 1 < len(args) else None
        if arg == "--":
            o.words.extend(args[i + 1 :])
            break
        if arg == "--raw":
            o.raw = True
        elif arg in ("--tools", "-t"):
            o.enable_tools = True
        elif arg in ("--no-tools", "-nt", "--without-tools"):
            o.enable_tools = False
        elif arg == "--new":
            o.session_mode = "new"
        elif arg == "--no-session":
            o.session_mode = "none"
        elif arg in ("-c", "--copy"):
            o.copy = True
        elif arg == "--json":
            o.json = True
        elif arg == "--no-context":
            o.use_context = False
        elif arg == "--print":
            o.print_only = True
        elif arg in ("--all",):
            o.all_matches = True
        elif arg in ("-f", "--file") and nxt is not None:
            o.files.append(nxt)
            i += 1
        elif arg.startswith("--file="):
            o.files.append(arg.split("=", 1)[1])
        elif arg in ("-a", "--agent", "--harness") and nxt is not None:
            o.harness = nxt
            i += 1
        elif arg in ("-m", "--model") and nxt is not None:
            o.model = nxt
            i += 1
        elif arg.startswith(("--agent=", "--harness=")):
            o.harness = arg.split("=", 1)[1]
        elif arg.startswith("--model="):
            o.model = arg.split("=", 1)[1]
        elif arg in ("-H", "--handoff"):
            o.handoff = True
            if nxt is not None and nxt.lower() in HARNESS_REGISTRY:
                o.handoff_harness = nxt.lower()
                i += 1
        elif arg.startswith("--handoff="):
            o.handoff = True
            o.handoff_harness = arg.split("=", 1)[1].strip().lower() or None
        else:
            o.words.append(arg)
        i += 1
    return o


def _read_stdin() -> str:
    if sys.stdin.isatty():
        return ""
    try:
        return sys.stdin.read().strip()
    except (OSError, UnicodeDecodeError):
        return ""


def _compose_prompt(opts: Options, body: str) -> str:
    """Prepend context files and -f files to the prompt body."""
    from ai_cli import extras

    sections = []
    if opts.use_context:
        ctx = extras.build_context_block(CONFIG_DIR)
        if ctx:
            sections.append(ctx)
    if opts.files:
        block, warnings = extras.expand_file_args(opts.files)
        for w in warnings:
            sys.stderr.write(f"ai: {w}\n")
        if block:
            sections.append(f"## Files\n{block}")
    sections.append(body)
    return "\n\n".join(s for s in sections if s)


def query_harness(
    opts: Options, prompt: str, console: Any | None = None, status: str = "Thinking"
) -> tuple[str, str, float]:
    """Resolve harness, run the prompt. Returns (stdout, harness_name, seconds)."""
    import time

    harness_name = resolve_harness(opts.harness, console=console)
    if not shutil.which(harness_name):
        _harness_missing_error(harness_name)
    builder = HARNESS_REGISTRY[harness_name]["builder"]
    cmd = builder(opts.model, opts.enable_tools, prompt, session_mode=opts.session_mode)

    t0 = time.monotonic()
    if console is not None:
        with console.status(f"[bold blue]{status} ({harness_name})...[/bold blue]", spinner="dots"):
            out, err = _run_harness(cmd)
    else:
        out, err = _run_harness(cmd)
    elapsed = time.monotonic() - t0
    parser = HARNESS_REGISTRY[harness_name].get("output_parser")
    if parser and out:
        out = parser(out, session_mode=opts.session_mode)
    if not out and err:
        sys.stderr.write(err)
    return out or "", harness_name, elapsed


def _footer(console: Any | None, harness: str, model: str | None, seconds: float) -> None:
    if os.environ.get("AI_NO_FOOTER"):
        return
    text = f"{harness}{' · ' + model if model else ''} · {seconds:.1f}s"
    if console is not None:
        console.print(f"[grey50]{text}[/grey50]", justify="right", highlight=False)
    elif sys.stderr.isatty():
        sys.stderr.write(f"\x1b[90m{text}\x1b[0m\n")


def _emit(opts: Options, out: str, harness: str, seconds: float, console: Any | None) -> None:
    """Print a normal answer in the requested format, then handle --copy and footer."""
    from ai_cli import extras

    if opts.json:
        payload = {
            "response": out.strip(),
            "harness": harness,
            "model": opts.model,
            "seconds": round(seconds, 2),
        }
        code = extras.first_code_block(out)
        if code is not None:
            payload["code"] = code
        print(json.dumps(payload, ensure_ascii=False))
    elif console is not None:
        if out:
            render_mixed_markdown_with_math(out.strip(), console)
    elif out:
        sys.stdout.write(sanitize_inline_math(out))
        if not out.endswith("\n"):
            sys.stdout.write("\n")
        sys.stdout.flush()

    if opts.copy and out:
        code = extras.first_code_block(out)
        tool = extras.copy_to_clipboard(code if code is not None else out.strip())
        what = "code block" if code is not None else "answer"
        msg = f"✓ copied {what} ({tool})" if tool else "✗ no clipboard tool found (install wl-clipboard)"
        sys.stderr.write(f"\x1b[90m{msg}\x1b[0m\n" if sys.stderr.isatty() else msg + "\n")

    if not opts.json:
        _footer(console, harness, opts.model, seconds)


def _console_for(opts: Options) -> Any | None:
    render = sys.stdout.isatty() and not opts.raw and not opts.json and HAS_RICH
    return _make_console() if render else None


# --- subcommands -----------------------------------------------------------------


def cmd_explain(opts: Options) -> None:
    from ai_cli import extras

    piped = _read_stdin()
    if not piped and not opts.prompt and not opts.files:
        sys.stderr.write("usage: <command> 2>&1 | ai explain [extra question]\n")
        sys.exit(2)
    body = f"{extras.EXPLAIN_PROMPT}\n\n```\n{piped}\n```" if piped else extras.EXPLAIN_PROMPT
    if opts.prompt:
        body = f"{body}\n\n{opts.prompt}"
    console = _console_for(opts)
    out, harness, secs = query_harness(opts, _compose_prompt(opts, body), console, status="Explaining")
    _emit(opts, out, harness, secs, console)


def cmd_do(opts: Options) -> None:
    from ai_cli import extras

    request = opts.prompt or _read_stdin()
    if not request:
        sys.stderr.write("usage: ai do <what you want to do>\n")
        sys.exit(2)
    shell = os.path.basename(os.environ.get("SHELL", "sh"))
    os_name = "Linux" if sys.platform.startswith("linux") else sys.platform
    prompt = extras.DO_PROMPT.format(shell=shell, os_name=os_name, cwd=os.getcwd(), request=request)
    opts.enable_tools = False
    opts.session_mode = "none"
    console = None if opts.print_only else _console_for(opts)
    out, harness, secs = query_harness(opts, _compose_prompt(opts, prompt), console, status="Thinking")
    command = extras.clean_single_command(out)
    if not command:
        sys.stderr.write("ai: no command produced\n")
        sys.exit(1)

    if opts.print_only or opts.json:
        print(json.dumps({"command": command, "harness": harness, "seconds": round(secs, 2)}) if opts.json else command)
        return
    if opts.copy:
        extras.copy_to_clipboard(command)

    if console is not None:
        from rich.syntax import Syntax

        console.print(Syntax(command, "bash", theme="ansi_dark", background_color="default", word_wrap=True))
    else:
        sys.stderr.write(f"$ {command}\n")
    _footer(console, harness, opts.model, secs)

    if not os.isatty(0) and not _reopen_tty():
        print(command)
        return
    choice = extras.ask_choice("Run it? [Y/e/n] ")
    if choice == "e":
        command = extras.edit_line(command)
        choice = "y" if command else "n"
    if choice != "y":
        sys.exit(1)
    _append_shell_history(command)
    sys.exit(subprocess.call(command, shell=True, executable=os.environ.get("SHELL") or None))


def _reopen_tty() -> bool:
    """When stdin was piped, reattach it to the terminal for the confirm prompt."""
    try:
        fd = os.open("/dev/tty", os.O_RDONLY)
    except OSError:
        return False
    os.dup2(fd, 0)
    os.close(fd)
    sys.stdin = open(0, closefd=False)
    return True


def _append_shell_history(command: str) -> None:
    """Best effort: add the executed command to zsh/bash history file."""
    import time

    shell = os.path.basename(os.environ.get("SHELL", ""))
    histfile = os.environ.get("HISTFILE") or str(Path.home() / (".zsh_history" if shell == "zsh" else ".bash_history"))
    try:
        with open(histfile, "a", encoding="utf-8") as f:
            if shell == "zsh":
                f.write(f": {int(time.time())}:0;{command}\n")
            else:
                f.write(command + "\n")
    except OSError:
        pass


def cmd_commit(opts: Options) -> None:
    from ai_cli import extras

    diff = extras.staged_diff()
    if diff is None:
        sys.stderr.write("ai commit: nothing staged (git add first) or not a git repository\n")
        sys.exit(1)
    body = f"{extras.COMMIT_PROMPT}\n\nRecent commits:\n{extras.recent_commits()}\n\nStaged diff:\n```diff\n{diff}\n```"
    if opts.prompt:
        body += f"\n\nExtra instruction: {opts.prompt}"
    opts.enable_tools = False
    opts.session_mode = "none"
    console = None if opts.print_only else _console_for(opts)
    out, harness, secs = query_harness(opts, _compose_prompt(opts, body), console, status="Writing commit")
    message = extras.clean_commit_message(out)
    if not message:
        sys.stderr.write("ai commit: empty message\n")
        sys.exit(1)
    if opts.print_only or not sys.stdin.isatty():
        print(message)
        return

    if console is not None:
        from rich.panel import Panel

        console.print(Panel(message, title="commit message", border_style="grey50", expand=False))
    else:
        print(f"\n{message}\n")
    _footer(console, harness, opts.model, secs)

    choice = extras.ask_choice("Commit? [Y/e/n] ")
    if choice == "n":
        sys.exit(1)
    if choice == "e":
        sys.exit(subprocess.call(["git", "commit", "-e", "-m", message]))
    sys.exit(subprocess.call(["git", "commit", "-m", message]))


def cmd_log(opts: Options) -> None:
    from ai_cli import extras

    sessions = extras.list_sessions(CACHE_DIR)
    query = opts.prompt.lower()
    if query:
        sessions = [
            s for s in sessions
            if query in s["title"].lower()
            or any(query in m["content"].lower() for m in extras.read_session_messages(Path(s["path"])))
        ]
    if not sessions:
        sys.stderr.write("ai log: no sessions found" + (f" matching '{opts.prompt}'" if query else "") + "\n")
        sys.exit(1)

    if opts.json:
        print(json.dumps([{k: v for k, v in s.items() if k != "mtime"} for s in sessions], ensure_ascii=False))
        return

    interactive = sys.stdout.isatty() and sys.stdin.isatty() and shutil.which("fzf") and not opts.all_matches
    if interactive:
        chosen = extras.pick_session_fzf(sessions)
        if chosen:
            _show_session(Path(chosen), opts)
        return
    for s in sessions:
        print(f"{s['when']}  {s['harness']:<8} {s['turns']:>3}×  {s['title']}")


def _show_session(path: Path, opts: Options) -> None:
    from ai_cli import extras

    text = extras.format_transcript(extras.read_session_messages(path))
    console = _console_for(opts)
    if console is not None:
        render_mixed_markdown_with_math(text, console)
    else:
        print(text)


def main() -> None:
    args = sys.argv[1:]

    if args and args[0] in ("-V", "--version"):
        from ai_cli import __version__

        print(f"ai-flow-cli {__version__}")
        sys.exit(0)

    if args[:1] == ["--zsh"]:
        from ai_cli.extras import ZSH_SNIPPET

        print(ZSH_SNIPPET)
        sys.exit(0)

    if args[:1] == ["--show-session"] and len(args) > 1:
        _show_session(Path(args[1]), parse_args(args[2:]))
        sys.exit(0)

    # Check for wizard flag immediately
    if "--wizard" in args:
        run_harness_wizard(console=_make_console(), current_harness=load_config().get("harness"))
        sys.exit(0)

    # Check for clear session flag
    if "--clear" in args:
        clear_terminal_session()
        print("Session cleared for this terminal.")
        sys.exit(0)

    if not args and sys.stdin.isatty():
        print_help()
        sys.exit(0)

    # Help: `ai --help`, `ai help [cmd]`, `ai <cmd> --help` (flags before "--" only)
    head = args[: args.index("--")] if "--" in args else args
    if args[:1] == ["help"]:
        print_help(args[1] if len(args) > 1 else None)
        sys.exit(0)
    if any(arg in ("-h", "--help") for arg in head):
        print_help(args[0] if args and args[0] in SUBCOMMANDS else None)
        sys.exit(0)

    # Subcommands: first word only, and `ai do you know ...` stays a question.
    if args and args[0] in SUBCOMMANDS:
        sub = args[0]
        rest = args[1:]
        is_question = sub == "do" and rest[:1] and rest[0].lower() in _do_question_words()
        if not is_question:
            opts = parse_args(rest)
            if sub == "log" and opts.harness is not None and opts.harness not in HARNESS_REGISTRY:
                # `ai log -a rojo`: -a means "print all" here, not --agent
                opts.all_matches = True
                opts.words.insert(0, opts.harness)
                opts.harness = None
            elif sub == "log" and "-a" in rest and opts.harness is None:
                opts.all_matches = True
            {"do": cmd_do, "commit": cmd_commit, "explain": cmd_explain, "log": cmd_log}[sub](opts)
            return

    opts = parse_args(args)
    prompt = opts.prompt

    stdin_content = _read_stdin()
    if stdin_content:
        prompt = f"{stdin_content}\n\n{prompt}" if prompt else stdin_content

    # Handoff mode: transfer context to harness TUI and open it
    if opts.handoff:
        target = opts.handoff_harness or opts.harness or resolve_harness(None, console=_make_console())
        execute_handoff(target_harness=target, extra_instruction=prompt)
        return

    if not prompt and not opts.files:
        print_help()
        sys.exit(1)

    console = _console_for(opts)
    full_prompt = _compose_prompt(opts, prompt or "Review these files.")
    out, harness, secs = query_harness(opts, full_prompt, console)
    _emit(opts, out, harness, secs, console)


if __name__ == "__main__":
    main()
