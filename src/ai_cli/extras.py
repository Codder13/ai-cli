"""Helpers for the everyday extras: commit, do, explain, log, files, context, clipboard, zsh.

Kept free of heavy imports so `ai` startup stays fast.
"""

from __future__ import annotations

import glob
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

# --- limits ----------------------------------------------------------------------

CONTEXT_MAX_BYTES = 16_000
FILE_MAX_BYTES = 200_000
FILES_TOTAL_MAX_BYTES = 1_000_000
DIFF_MAX_BYTES = 60_000

# Words that make "ai do <word> ..." a normal question ("ai do you know ...").
DO_QUESTION_WORDS = frozenset({"you", "i", "we", "they", "it", "u", "not", "people", "cats", "dogs"})

# --- prompts ---------------------------------------------------------------------

EXPLAIN_PROMPT = (
    "Explain the following command output or error concisely: what went wrong and why, "
    "then how to fix it. If there is a fix command, show it in a code block."
)

DO_PROMPT = (
    "Translate the request into ONE shell command for {shell} on {os_name}. "
    "Working directory: {cwd}. Output ONLY the command on a single line: no explanation, "
    "no markdown, no code fences. Chain with && or pipes if needed. "
    "If the request is unsafe or impossible, output a command that is `echo` of the reason.\n\n"
    "Request: {request}"
)

COMMIT_PROMPT = (
    "Write a git commit message for the staged diff below. Use Conventional Commits "
    "(type(scope): subject), imperative mood, subject max 72 chars. Add a short body "
    "(wrapped at 72) only when the change needs explaining. Match the style of the recent "
    "commits. Output ONLY the commit message: no code fences, no commentary."
)


# --- per-directory context (.ai.md) ---------------------------------------------


def _read_capped(path: Path, limit: int) -> str:
    try:
        data = path.read_bytes()[: limit + 1]
    except OSError:
        return ""
    text = data[:limit].decode("utf-8", errors="replace").strip()
    if len(data) > limit:
        text += "\n[... truncated]"
    return text


def find_project_context(start: Path | None = None) -> Path | None:
    """Nearest `.ai.md` walking up from cwd, stopping at $HOME or the filesystem root."""
    cur = (start or Path.cwd()).resolve()
    home = Path.home().resolve()
    while True:
        candidate = cur / ".ai.md"
        if candidate.is_file():
            return candidate
        if cur == home or cur.parent == cur:
            return None
        cur = cur.parent


def build_context_block(config_dir: Path, start: Path | None = None) -> str:
    """Global (~/.config/ai/context.md) + nearest project .ai.md, as a prompt preamble."""
    parts = []
    global_ctx = config_dir / "context.md"
    if global_ctx.is_file():
        text = _read_capped(global_ctx, CONTEXT_MAX_BYTES)
        if text:
            parts.append(f"## User context ({global_ctx})\n{text}")
    project = find_project_context(start)
    if project and project != global_ctx:
        text = _read_capped(project, CONTEXT_MAX_BYTES)
        if text:
            parts.append(f"## Project context ({project})\n{text}")
    return "\n\n".join(parts)


# --- -f / --file globs -------------------------------------------------------------


def _is_binary(path: Path) -> bool:
    try:
        with open(path, "rb") as f:
            return b"\0" in f.read(2048)
    except OSError:
        return True


def expand_file_args(patterns: list[str]) -> tuple[str, list[str]]:
    """Expand globs into fenced file blocks. Returns (block, warnings)."""
    seen: list[Path] = []
    warnings: list[str] = []
    for pattern in patterns:
        matches = sorted(glob.glob(os.path.expanduser(pattern), recursive=True))
        if not matches:
            warnings.append(f"no files match '{pattern}'")
        for m in matches:
            p = Path(m)
            if p.is_file() and p not in seen:
                seen.append(p)

    blocks: list[str] = []
    total = 0
    for p in seen:
        if _is_binary(p):
            warnings.append(f"skipped binary file {p}")
            continue
        if total >= FILES_TOTAL_MAX_BYTES:
            warnings.append(f"total size limit reached, skipped {p} and the rest")
            break
        text = _read_capped(p, min(FILE_MAX_BYTES, FILES_TOTAL_MAX_BYTES - total))
        total += len(text.encode())
        lang = p.suffix.lstrip(".")
        blocks.append(f"### {p}\n```{lang}\n{text}\n```")
    return "\n\n".join(blocks), warnings


# --- output helpers --------------------------------------------------------------

_FENCE_RE = re.compile(r"```[^\n`]*\n(.*?)```", re.S)


def first_code_block(text: str) -> str | None:
    m = _FENCE_RE.search(text)
    return m.group(1).rstrip("\n") if m else None


def clean_single_command(text: str) -> str:
    """Turn a model answer into one runnable command line."""
    block = first_code_block(text)
    body = block if block is not None else text
    lines = [ln.strip() for ln in body.strip().splitlines() if ln.strip()]
    lines = [ln for ln in lines if not ln.startswith("#")] or lines
    cmd = " && ".join(lines) if len(lines) > 1 and block is not None else (lines[0] if lines else "")
    cmd = cmd.strip().strip("`").strip()
    if cmd.startswith("$ "):
        cmd = cmd[2:]
    return cmd


def clean_commit_message(text: str) -> str:
    block = first_code_block(text)
    msg = (block if block is not None else text).strip()
    return msg.strip("`").strip()


def copy_to_clipboard(text: str) -> str | None:
    """Copy using wl-copy / xclip / xsel / pbcopy. Returns the tool used, or None."""
    candidates = []
    if os.environ.get("WAYLAND_DISPLAY"):
        candidates.append(["wl-copy"])
    candidates += [["xclip", "-selection", "clipboard"], ["xsel", "--clipboard", "--input"], ["pbcopy"]]
    if not os.environ.get("WAYLAND_DISPLAY"):
        candidates.append(["wl-copy"])
    for cmd in candidates:
        if shutil.which(cmd[0]):
            try:
                subprocess.run(cmd, input=text, text=True, check=True, timeout=5)
                return cmd[0]
            except (OSError, subprocess.SubprocessError):
                continue
    return None


# --- interactive confirm ---------------------------------------------------------


def ask_choice(question: str, default: str = "y") -> str:
    """[Y/e/n] prompt read from the terminal. Returns 'y', 'e' or 'n'."""
    try:
        ans = input(question).strip().lower()
    except (EOFError, KeyboardInterrupt):
        sys.stderr.write("\n")
        return "n"
    return (ans or default)[0] if (ans or default)[0] in "yen" else "n"


def edit_line(initial: str, prompt: str = "> ") -> str:
    """Let the user edit a line in place (readline prefill)."""
    try:
        import readline

        readline.set_startup_hook(lambda: readline.insert_text(initial))
        try:
            return input(prompt).strip()
        finally:
            readline.set_startup_hook()
    except (ImportError, EOFError, KeyboardInterrupt):
        return initial


# --- git helpers -----------------------------------------------------------------


def git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], capture_output=True, text=True)


def staged_diff() -> str | None:
    """Staged diff (capped), or None when not in a git repo / nothing staged."""
    if not shutil.which("git") or git("rev-parse", "--is-inside-work-tree").returncode != 0:
        return None
    diff = git("diff", "--staged", "--no-color").stdout
    if not diff.strip():
        return None
    if len(diff) > DIFF_MAX_BYTES:
        stat = git("diff", "--staged", "--stat", "--no-color").stdout
        diff = f"{stat}\n{diff[:DIFF_MAX_BYTES]}\n[... diff truncated]"
    return diff


def recent_commits(n: int = 10) -> str:
    return git("log", f"-{n}", "--pretty=format:%s").stdout.strip()


# --- session log -----------------------------------------------------------------


def read_session_messages(path: Path) -> list[dict[str, str]]:
    from ai_cli.main import _extract_text_from_content

    messages: list[dict[str, str]] = []
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(data, dict) and data.get("type") == "message":
                    msg = data.get("message", {})
                    if msg.get("role") in ("user", "assistant"):
                        text = _extract_text_from_content(msg.get("content")).strip()
                        if text:
                            messages.append({"role": msg["role"], "content": text})
    except OSError:
        pass
    return messages


def _first_user_line(messages: list[dict[str, str]]) -> str:
    for m in messages:
        if m["role"] == "user":
            # skip the context preamble we inject
            text = m["content"]
            if text.startswith("## ") and "\n\n" in text:
                text = text.rsplit("\n\n", 1)[-1]
            return " ".join(text.split())[:100]
    return "(empty)"


def list_sessions(cache_dir: Path) -> list[dict]:
    from datetime import datetime

    out = []
    for path in cache_dir.glob("*/*/*.jsonl"):
        msgs = read_session_messages(path)
        if not msgs:
            continue
        mtime = path.stat().st_mtime
        out.append(
            {
                "path": str(path),
                "harness": path.parent.parent.name,
                "when": datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M"),
                "mtime": mtime,
                "turns": sum(1 for m in msgs if m["role"] == "user"),
                "title": _first_user_line(msgs),
            }
        )
    return sorted(out, key=lambda s: s["mtime"], reverse=True)


def format_transcript(messages: list[dict[str, str]]) -> str:
    parts = []
    for m in messages:
        label = "**You**" if m["role"] == "user" else "**AI**"
        parts.append(f"{label}\n\n{m['content']}")
    return "\n\n---\n\n".join(parts)


def self_command() -> str:
    """Shell-quoted way to re-invoke this CLI (for fzf previews)."""
    argv0 = sys.argv[0] if sys.argv else ""
    if argv0 and os.path.isfile(argv0) and os.access(argv0, os.X_OK):
        return shlex.quote(os.path.abspath(argv0))
    return f"{shlex.quote(sys.executable)} -m ai_cli.main"


def pick_session_fzf(sessions: list[dict]) -> str | None:
    lines = [f"{s['path']}\t{s['when']}  {s['harness']:<8} {s['turns']:>3}×  {s['title']}" for s in sessions]
    preview = f"{self_command()} --show-session {{1}}"
    try:
        proc = subprocess.run(
            [
                "fzf", "--delimiter", "\t", "--with-nth", "2..", "--no-sort",
                "--prompt", "ai log> ", "--preview", preview,
                "--preview-window", "right,60%,wrap", "--height", "90%",
            ],
            input="\n".join(lines),
            text=True,
            stdout=subprocess.PIPE,
        )
    except OSError:
        return None
    if proc.returncode != 0 or not proc.stdout.strip():
        return None
    return proc.stdout.split("\t", 1)[0].strip()


# --- zsh widget --------------------------------------------------------------------

ZSH_SNIPPET = r"""# ai-flow-cli zsh integration — add to ~/.zshrc:
#   eval "$(ai --zsh)"
# Ctrl+G (or $AI_ZSH_KEY) turns the text on your command line into a shell command.
_ai_flow_widget() {
  [[ -z "$BUFFER" ]] && return
  local orig="$BUFFER" out
  BUFFER="⏳ $orig"; zle -R
  out=$(ai do --print -- "$orig" </dev/null 2>/dev/null)
  if [[ -n "$out" ]]; then BUFFER="$out"; else BUFFER="$orig"; fi
  CURSOR=${#BUFFER}
  zle -R
}
zle -N _ai_flow_widget
bindkey "${AI_ZSH_KEY:-^G}" _ai_flow_widget
"""
