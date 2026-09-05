#!/usr/bin/env python3
"""ai-cli: Fast CLI wrapper around omp for everyday queries and Unix pipelines."""

import os
import shutil
import subprocess
import sys

# Optional rich for beautiful markdown rendering in terminal
try:
    from rich.console import Console
    from rich.markdown import Markdown
    from rich.status import Status
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

def print_help() -> None:
    help_text = """ai - Fast terminal AI powered by omp

Usage:
  ai <prompt>                      Ask question / prompt
  ai "multi word prompt"           Ask question
  echo "data" | ai <prompt>        Pipe stdin context into prompt
  ai --help, -h                    Show this help
  ai --raw <prompt>                Print plain text without markdown styling
  ai --tools <prompt>              Run with tool execution enabled
  ai --model <name> <prompt>       Specify model for omp

Features:
  - Powered by omp harness (omp -p --no-session)
  - Rich terminal markdown rendering with code syntax highlighting
  - Pure PDF/LaTeX math rendering in supported terminals (Kitty graphics)
  - Clean Unicode unit conversion (e.g. ~21,196 km, ~200 km²)
  - Unix pipeline friendly (clean stdout passthrough when piped)

Examples:
  ai what is the biggest object on earth
  ai show me the quadratic formula
  git diff | ai review these changes
  cat server.log | ai find error root cause
"""
    print(help_text)


def main() -> None:
    args = sys.argv[1:]

    if not args and sys.stdin.isatty():
        print_help()
        sys.exit(0)

    # Check for help flag
    if any(arg in ("-h", "--help") for arg in args):
        print_help()
        sys.exit(0)

    # Check for omp in PATH
    if not shutil.which("omp"):
        sys.stderr.write("Error: 'omp' executable not found in PATH.\n")
        sys.stderr.write("Please install or ensure omp is available in your PATH.\n")
        sys.exit(1)

    # Parse our custom options
    raw_mode = False
    enable_tools = False
    model_override = None
    pass_through_args = []
    prompt_words = []

    i = 0
    while i < len(args):
        arg = args[i]
        if arg == "--raw":
            raw_mode = True
            i += 1
        elif arg == "--tools":
            enable_tools = True
            i += 1
        elif arg in ("-m", "--model"):
            if i + 1 < len(args):
                model_override = args[i + 1]
                i += 2
            else:
                prompt_words.append(arg)
                i += 1
        elif arg.startswith("--model="):
            model_override = arg.split("=", 1)[1]
            i += 1
        else:
            prompt_words.append(arg)
            i += 1

    prompt = " ".join(prompt_words).strip()

    # Handle piped stdin
    stdin_content = ""
    if not sys.stdin.isatty():
        try:
            stdin_content = sys.stdin.read().strip()
        except Exception:
            pass

    if stdin_content:
        if prompt:
            prompt = f"{stdin_content}\n\n{prompt}"
        else:
            prompt = stdin_content

    if not prompt:
        print_help()
        sys.exit(1)

    # Build omp command: omp -p --no-session
    cmd = ["omp", "-p", "--no-session"]

    if not enable_tools:
        cmd.append("--no-tools")
    else:
        cmd.append("--auto-approve")

    # Prompt convention: use normal LaTeX display math ($$ ... $$) for equations,
    # but use normal units (~21,196 km) in conversational text.
    cmd.extend([
        "--append-system-prompt",
        "Formatting instructions: For mathematical equations, display formulas, or matrices, use standard LaTeX block math ($$ ... $$ or \\[ ... \\]). For plain physical units, numbers, and measurements in text, write normal readable text without math dollar signs (e.g. ~21,196 km, 65.5 million tons, 200 km²)."
    ])

    if model_override:
        cmd.extend(["--model", model_override])

    if pass_through_args:
        cmd.extend(pass_through_args)

    cmd.append(prompt)

    # Terminal output checking
    is_interactive_terminal = sys.stdout.isatty() and not raw_mode and HAS_RICH

    console = Console() if HAS_RICH else None

    if is_interactive_terminal and console:
        # Show clean spinner on stderr while omp processes
        status = console.status("[bold blue]Thinking...[/bold blue]", spinner="dots")
        status.start()
        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            stdout_data, stderr_data = proc.communicate()
        finally:
            status.stop()

        if proc.returncode != 0:
            if stderr_data:
                sys.stderr.write(stderr_data)
            sys.exit(proc.returncode)

        if stdout_data:
            render_mixed_markdown_with_math(stdout_data.strip(), console)
        elif stderr_data:
            sys.stderr.write(stderr_data)
    else:
        # Piped stdout or raw mode or no rich: direct output
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        stdout_data, stderr_data = proc.communicate()
        if proc.returncode != 0:
            if stderr_data:
                sys.stderr.write(stderr_data)
            sys.exit(proc.returncode)

        if stdout_data:
            clean_output = sanitize_inline_math(stdout_data)
            sys.stdout.write(clean_output)
            sys.stdout.flush()
        elif stderr_data:
            sys.stderr.write(stderr_data)


if __name__ == "__main__":
    main()
