"""
LaTeX math post-processing and rendering helpers.

Converts LaTeX formulas and notation to readable Unicode/terminal text
matching Oh My Pi (omp) native rendering.

Heavy dependencies (rich, pylatexenc) are imported lazily so that the plain
pipe / ``--raw`` path and ``ai --help`` stay fast.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from rich.console import Console

# Path to the bundled JS math engine (vendored from omp)
OMP_MATH_SCRIPT = Path(__file__).resolve().parent / "omp_math.mjs"

TEXT_MACRO_RE = re.compile(r"\\text\{([^}]+)\}")
SIM_RE = re.compile(r"\\sim\s*")
TIMES_RE = re.compile(r"\\times\s*")
THOUSANDS_RE = re.compile(r"\{,\}")
EXPONENT_RE = re.compile(r"\^\{?([0-9+-]+)\}?")
SIMPLE_DOLLAR_RE = re.compile(r"\$([0-9.,~×\s\w]+)\$")
DISPLAY_MATH_RE = re.compile(r"(\$\$(?:\\.|[^\$])+\$\$|\\\[(?:\\.|[^\]])+\\\])")

# Cheap pre-check: only spawn the JS renderer when the text can contain math.
MATH_DELIMITER_RE = re.compile(r"\$|\\\(|\\\[")

SUPERSCRIPTS = str.maketrans("0123456789+-", "⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻")


def has_math(text: str) -> bool:
    """Return True if text contains any LaTeX math delimiter."""
    return MATH_DELIMITER_RE.search(text) is not None


def render_math_with_omp(text: str) -> str:
    """
    Render LaTeX math notation in text using omp's bundled parser logic.

    Executes via bun or node if available. Returns the original text when
    there is no math, no JS runtime, or on any error.
    """
    if not has_math(text) or not OMP_MATH_SCRIPT.exists():
        return text

    js_runtime = shutil.which("bun") or shutil.which("node")
    if not js_runtime:
        return text

    try:
        proc = subprocess.run(
            [js_runtime, str(OMP_MATH_SCRIPT)],
            input=text,
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return text

    if proc.returncode == 0 and proc.stdout:
        return proc.stdout
    return text


def sanitize_inline_math(text: str) -> str:
    """
    Normalize simple inline math units and symbols so they don't break
    standard terminal output or markdown rendering.
    """
    # Fix unit measurements: $\sim 21{,}196\text{ km}$ -> ~21,196 km
    text = TEXT_MACRO_RE.sub(r"\1", text)
    text = SIM_RE.sub("~", text)
    text = TIMES_RE.sub("×", text)
    text = THOUSANDS_RE.sub(",", text)

    # Exponents: m^3 -> m³, x^2 -> x²
    text = EXPONENT_RE.sub(lambda m: m.group(1).translate(SUPERSCRIPTS), text)

    # Remove remaining standalone $ if they are wrapping simple numbers/units
    return SIMPLE_DOLLAR_RE.sub(r"\1", text)


def _convert_display_math_pylatexenc(text: str) -> str:
    """Fallback: convert $$...$$ / \\[...\\] blocks with pylatexenc, if installed."""
    try:
        from pylatexenc.latex2text import LatexNodes2Text
    except ImportError:
        return text

    l2t = LatexNodes2Text(math_mode="text")

    def _convert(m: re.Match[str]) -> str:
        raw = m.group(0).strip()
        inner = raw[2:-2].strip()  # both "$$" and "\[" / "\]" are 2 chars
        try:
            converted = l2t.latex_to_text(inner).strip()
        except Exception:  # noqa: BLE001 - pylatexenc raises assorted errors
            return raw
        return f"\n\n{converted}\n\n" if converted else raw

    return DISPLAY_MATH_RE.sub(_convert, text)


def render_mixed_markdown_with_math(text: str, console: Console) -> None:
    """
    Render text by converting LaTeX math (display blocks and inline) to
    Unicode using omp's renderer (or the pylatexenc fallback), then print it
    as Rich markdown.
    """
    from rich.markdown import Markdown

    if has_math(text):
        omp_rendered = render_math_with_omp(text)
        if omp_rendered != text:
            console.print(Markdown(omp_rendered, code_theme="monokai"))
            return
        text = _convert_display_math_pylatexenc(text)

    text = sanitize_inline_math(text)
    console.print(Markdown(text, code_theme="monokai"))
