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

# Order used when no harness is configured: first one found in PATH wins.
HARNESS_PREFERENCE = ("pi", "omp", "claude", "codex", "copilot", "opencode")

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

    # Fallback: if no session files found for this tab, check most recent session file anywhere in CACHE_DIR
    if not session_files and CACHE_DIR.is_dir():
        session_files = list(CACHE_DIR.glob("*/*/*.jsonl"))

    if not session_files:
        return []

    # Pick the most recently modified session file
    latest_file = max(session_files, key=lambda p: p.stat().st_mtime)

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


def print_help() -> None:
    supported = ", ".join(HARNESS_REGISTRY.keys())
    help_text = f"""ai - Fast terminal AI for questions, pipelines & code assistance

Usage:
  ai <question or prompt>
  ai [options] <question or prompt>
  cat file | ai <question or prompt>
  git diff | ai "review these changes"

Options:
  --raw                  Output raw text directly without markdown rendering
  --no-tools, -nt        Disable tool execution so the AI has no access to tools
  --tools, -t            Enable tool execution / auto-approval (default: enabled)
  --new                  Start a new session for this terminal (wipe previous context)
  --no-session           Run ephemerally without persisting or resuming session history
  --clear                Clear session history for current terminal tab and exit
  -a, --agent <name>     Use specific agent harness ({supported})
  -H, --handoff [name]   Handoff current session context to harness TUI
  --wizard               Interactive selector to choose and save default harness
  -m, --model <name>     Specify model name override
  -V, --version          Show version and exit
  -h, --help             Show this help message
  --                     Stop option parsing; everything after is the prompt

Environment:
  AI_HARNESS             Default harness (overrides ~/.config/ai/config.json)

Session Persistence:
  Queries in the same terminal tab/pane automatically share context.
  Use --new or --clear to reset, or --no-session for one-off ephemeral questions.

Examples:
  ai "how do I extract a .tar.gz file?"
  ai "what was the command you just suggested?"
  ai --new "start a completely different topic"
  cat main.py | ai "explain what this code does"
  git diff | ai "write a concise commit message for this diff"
  ai -a claude "how to optimize this query?"
  ai -H omp "continue this task and write the files"
  ai -H claude
  ai --wizard
"""
    print(help_text)


def _run_harness(cmd: list[str]) -> tuple[str, str]:
    """Run the harness, returning (stdout, stderr). Exits on failure."""
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
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


def main() -> None:
    args = sys.argv[1:]

    if args and args[0] in ("-V", "--version"):
        from ai_cli import __version__

        print(f"ai-flow-cli {__version__}")
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

    # Check for help flag
    if any(arg in ("-h", "--help") for arg in args):
        print_help()
        sys.exit(0)

    # Parse our custom options
    raw_mode = False
    enable_tools = True
    session_mode = "auto"
    model_override = None
    cli_harness = None
    handoff_mode = False
    handoff_harness = None
    prompt_words = []

    i = 0
    while i < len(args):
        arg = args[i]
        if arg == "--":
            prompt_words.extend(args[i + 1 :])
            break
        if arg == "--raw":
            raw_mode = True
        elif arg in ("--tools", "-t"):
            enable_tools = True
        elif arg in ("--no-tools", "-nt", "--without-tools"):
            enable_tools = False
        elif arg == "--new":
            session_mode = "new"
        elif arg == "--no-session":
            session_mode = "none"
        elif arg in ("-a", "--agent", "--harness", "-m", "--model"):
            if i + 1 < len(args):
                if arg in ("-m", "--model"):
                    model_override = args[i + 1]
                else:
                    cli_harness = args[i + 1]
                i += 1
            else:
                prompt_words.append(arg)
        elif arg.startswith(("--agent=", "--harness=")):
            cli_harness = arg.split("=", 1)[1]
        elif arg.startswith("--model="):
            model_override = arg.split("=", 1)[1]
        elif arg in ("-H", "--handoff"):
            handoff_mode = True
            nxt = args[i + 1].lower() if i + 1 < len(args) else ""
            if nxt in HARNESS_REGISTRY:
                handoff_harness = nxt
                i += 1
        elif arg.startswith("--handoff="):
            handoff_mode = True
            handoff_harness = arg.split("=", 1)[1].strip().lower() or None
        else:
            prompt_words.append(arg)
        i += 1

    prompt = " ".join(prompt_words).strip()

    # Handle piped stdin
    stdin_content = ""
    if not sys.stdin.isatty():
        try:
            stdin_content = sys.stdin.read().strip()
        except (OSError, UnicodeDecodeError):
            pass

    if stdin_content:
        prompt = f"{stdin_content}\n\n{prompt}" if prompt else stdin_content

    # Handoff mode: transfer context to harness TUI and open it
    if handoff_mode:
        target = handoff_harness or cli_harness or resolve_harness(None, console=_make_console())
        execute_handoff(target_harness=target, extra_instruction=prompt)
        return

    if not prompt:
        print_help()
        sys.exit(1)

    # Only build a Rich console when we will actually render to a terminal.
    render = sys.stdout.isatty() and not raw_mode and HAS_RICH
    console = _make_console() if render else None

    harness_name = resolve_harness(cli_harness, console=console)
    if not shutil.which(harness_name):
        _harness_missing_error(harness_name)

    builder = HARNESS_REGISTRY[harness_name]["builder"]
    cmd = builder(model_override, enable_tools, prompt, session_mode=session_mode)

    if render and console is not None:
        # Show clean spinner while harness processes
        with console.status(f"[bold blue]Thinking ({harness_name})...[/bold blue]", spinner="dots"):
            stdout_data, stderr_data = _run_harness(cmd)
        if stdout_data:
            render_mixed_markdown_with_math(stdout_data.strip(), console)
        elif stderr_data:
            sys.stderr.write(stderr_data)
    else:
        # Piped stdout or raw mode or no rich: direct output
        stdout_data, stderr_data = _run_harness(cmd)
        if stdout_data:
            sys.stdout.write(sanitize_inline_math(stdout_data))
            sys.stdout.flush()
        elif stderr_data:
            sys.stderr.write(stderr_data)


if __name__ == "__main__":
    main()
