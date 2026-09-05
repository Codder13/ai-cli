#!/usr/bin/env python3
"""ai-cli: Fast CLI wrapper around omp for everyday queries and Unix pipelines."""

import os
import re
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

Examples:
  ai what is the biggest object on earth
  git diff | ai review these changes
  cat server.log | ai find error root cause
"""
    print(help_text)


def convert_latex_math(text: str) -> str:
    """Convert LaTeX math syntax emitted by models to readable Unicode/Markdown for terminals."""
    # 1. Protect code blocks (fenced ``` and inline `)
    code_tokens = []

    def save_code(m: re.Match) -> str:
        code_tokens.append(m.group(0))
        return f"__CODE_TOKEN_{len(code_tokens) - 1}__"

    text = re.sub(r"(```[\s\S]*?```|`[^`\n]+`)", save_code, text)

    # 2. Math replacer
    def format_math(m: re.Match) -> str:
        s = m.group(1).strip()

        # LaTeX en-dash / hyphens inside math
        s = s.replace(r"\text{--}", "–").replace("--", "–")

        # Superscripts: ^2, ^3, ^{10}, etc. before removing braces
        sup_map = {
            "0": "⁰", "1": "¹", "2": "²", "3": "³", "4": "⁴",
            "5": "⁵", "6": "⁶", "7": "⁷", "8": "⁸", "9": "⁹",
            "+": "⁺", "-": "⁻", "=": "⁼", "(": "⁽", ")": "⁾",
            "n": "ⁿ", "i": "ⁱ", "x": "ˣ"
        }

        def rep_sup(sm: re.Match) -> str:
            val = sm.group(1) or sm.group(2)
            if all(c in sup_map for c in val):
                return "".join(sup_map[c] for c in val)
            return "^" + val

        s = re.sub(r"\^\{([0-9+\-=()nix]+)\}", rep_sup, s)
        s = re.sub(r"\^([0-9nix])", rep_sup, s)

        # Subscripts: _2, _{10}
        sub_map = {
            "0": "₀", "1": "₁", "2": "₂", "3": "₃", "4": "₄",
            "5": "₅", "6": "₆", "7": "₇", "8": "₈", "9": "₉",
            "+": "₊", "-": "₋", "=": "₌", "(": "₍", ")": "₎",
            "a": "ₐ", "e": "ₑ", "o": "ₒ", "x": "ₓ", "h": "ₕ",
            "k": "ₖ", "l": "ₗ", "m": "ₘ", "n": "ₙ", "p": "ₚ",
            "s": "ₛ", "t": "ₜ"
        }

        def rep_sub(sm: re.Match) -> str:
            val = sm.group(1) or sm.group(2)
            if all(c in sub_map for c in val):
                return "".join(sub_map[c] for c in val)
            return "_" + val

        s = re.sub(r"_\{([0-9+\-=()aeoxhklmnpst]+)\}", rep_sub, s)
        s = re.sub(r"_([0-9aeoxhklmnpst])", rep_sub, s)

        # Text wrappers inside math: \text{ km} -> km
        s = re.sub(r"\\(?:text|mathrm|mathbf|mathit)\{([^}]*)\}", lambda tm: " " + tm.group(1).strip(), s)

        # Symbols to unicode
        symbols = [
            (r"\sim", "~"),
            (r"\approx", "≈"),
            (r"\times", "×"),
            (r"\pm", "±"),
            (r"\mp", "∓"),
            (r"\cdot", "·"),
            (r"\leq", "≤"),
            (r"\le", "≤"),
            (r"\geq", "≥"),
            (r"\ge", "≥"),
            (r"\neq", "≠"),
            (r"\ne", "≠"),
            (r"\infty", "∞"),
            (r"\degree", "°"),
            (r"\circ", "°"),
            (r"\alpha", "α"),
            (r"\beta", "β"),
            (r"\gamma", "γ"),
            (r"\delta", "δ"),
            (r"\pi", "π"),
            (r"\theta", "θ"),
            (r"\mu", "μ"),
            (r"\sigma", "σ"),
            (r"\Omega", "Ω"),
        ]
        for sym, rep in symbols:
            s = re.sub(re.escape(sym) + r"(?![a-zA-Z])", rep, s)

        # Thousands separator {,} -> ,
        s = s.replace("{,}", ",")

        # Fractions \frac{a}{b} -> (a/b)
        s = re.sub(r"\\frac\{([^}]+)\}\{([^}]+)\}", r"(\1/\2)", s)

        # Remove remaining lone braces and backslashes
        s = re.sub(r"[{}]", "", s)
        s = re.sub(r"\\([a-zA-Z]+)", r"\1", s)

        # Clean spaces
        s = re.sub(r"\s+", " ", s).strip()
        s = re.sub(r"~\s*", "~", s)
        s = re.sub(r"\s*–\s*", "–", s)
        return s

    # Convert display math $$...$$ and inline math $...$
    text = re.sub(r"\$\$([\s\S]*?)\$\$", format_math, text)
    text = re.sub(r"\$([^\$\n]+)\$", format_math, text)

    # Restore code blocks
    for idx, code in enumerate(code_tokens):
        text = text.replace(f"__CODE_TOKEN_{idx}__", code)

    return text


def main() -> None:
    args = sys.argv[1:]

    if not args or args[0] in ("-h", "--help"):
        print_help()
        sys.exit(0)

    # Check omp available
    if not shutil.which("omp"):
        sys.stderr.write("Error: 'omp' harness executable not found in PATH.\n")
        sys.stderr.write("Please install or ensure 'omp' is accessible in your environment.\n")
        sys.exit(1)

    raw_mode = False
    enable_tools = False
    model_override = None
    pass_through_args = []
    prompt_parts = []

    # Parse arguments
    i = 0
    while i < len(args):
        arg = args[i]
        if arg == "--raw":
            raw_mode = True
            i += 1
        elif arg == "--tools":
            enable_tools = True
            i += 1
        elif arg == "--model":
            if i + 1 < len(args):
                model_override = args[i + 1]
                i += 2
            else:
                sys.stderr.write("Error: --model requires an argument\n")
                sys.exit(1)
        elif arg.startswith("--"):
            pass_through_args.append(arg)
            i += 1
        else:
            prompt_parts.append(arg)
            i += 1

    prompt = " ".join(prompt_parts).strip()

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

    # Instruct model to avoid LaTeX math delimiters so terminal rendering is natural
    cmd.extend([
        "--append-system-prompt",
        "Terminal output formatting: NEVER use LaTeX math delimiters ($ or $$). Write numbers, measurements, and units in plain text or standard markdown (e.g. ~21,196 km, ~65.5 million tons, ~200 km²)."
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
            # Clean any LaTeX math markers ($...$, \text{...}, etc.)
            clean_output = convert_latex_math(stdout_data.strip())
            console.print(Markdown(clean_output))
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
            clean_output = convert_latex_math(stdout_data)
            sys.stdout.write(clean_output)
            sys.stdout.flush()
        elif stderr_data:
            sys.stderr.write(stderr_data)


if __name__ == "__main__":
    main()
