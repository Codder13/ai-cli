import os
import re
import sys
from rich.console import Console
from rich.markdown import Markdown
import subprocess
import shutil

OMP_MATH_SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "omp_math.mjs")

def render_math_with_omp(text: str) -> str:
    """
    Uses the exact oh-my-pi math-to-unicode engine extracted from omp
    via bun or node.
    """
    if not os.path.exists(OMP_MATH_SCRIPT):
        return text
    runner = shutil.which("bun") or shutil.which("node")
    if not runner:
        return text
    try:
        script = f"""
import {{ renderMath }} from "{OMP_MATH_SCRIPT}";
import fs from "fs";
const input = fs.readFileSync(0, "utf-8");
process.stdout.write(renderMath(input));
"""
        proc = subprocess.Popen(
            [runner, "-e", script],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        out, _ = proc.communicate(input=text, timeout=5)
        if proc.returncode == 0 and out:
            return out
    except Exception:
        pass
    return text

try:
    import pylatexenc.latex2text
    HAS_PYLATEXENC = True
except ImportError:
    HAS_PYLATEXENC = False
DISPLAY_MATH_RE = re.compile(
    r"""(
        \$\$([\s\S]+?)\$\$
        | \\\[([\s\S]+?)\\\]
        | \\begin\{(?:equation\*?|align\*?|gather\*?|multline\*?|cases\*?|pmatrix|bmatrix|vmatrix)\}[\s\S]+?\\end\{(?:equation\*?|align\*?|gather\*?|multline\*?|cases\*?|pmatrix|bmatrix|vmatrix)\}
    )""",
    re.VERBOSE,
)

SUPERSCRIPT_MAP = str.maketrans("0123456789+-=()n", "⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻⁼⁽⁾ⁿ")
SUBSCRIPT_MAP = str.maketrans("0123456789+-=()", "₀₁₂₃₄₅₆₇₈₉₊₋₌₍₎")

def parse_latex_colors(text: str) -> str:
    r"""
    Converts \textcolor{color}{text} and \colorbox{bg}{text} into ANSI escape sequences.
    """
    color_map = {
        "red": "31",
        "green": "32",
        "yellow": "33",
        "blue": "34",
        "magenta": "35",
        "purple": "35",
        "cyan": "36",
        "white": "37",
        "black": "30",
        "gray": "90",
        "grey": "90",
    }
    bg_map = {
        "yellow": "43",
        "red": "41",
        "green": "42",
        "blue": "44",
        "magenta": "45",
        "cyan": "46",
        "white": "47",
        "black": "40",
        "gray": "100",
    }

    def _replace_box(m: re.Match) -> str:
        bg = m.group(1).lower()
        inner = m.group(2)
        bg_code = bg_map.get(bg, "43")
        return f"\033[{bg_code}m{inner}\033[0m"

    def _replace_color(m: re.Match) -> str:
        color = m.group(1).lower()
        inner = m.group(2)
        fg_code = color_map.get(color, "37")
        return f"\033[{fg_code}m{inner}\033[0m"

    for _ in range(3):
        text = re.sub(r"\\colorbox\{([^}]+)\}\{((?:[^{}]|\{[^{}]*\})*)\}", _replace_box, text)
        text = re.sub(r"\\textcolor\{([^}]+)\}\{((?:[^{}]|\{[^{}]*\})*)\}", _replace_color, text)
    return text

def sanitize_inline_math(text: str) -> str:
    """
    Cleans LaTeX units and equations converting to Unicode text.
    """
    omp_rendered = render_math_with_omp(text)
    if omp_rendered != text:
        return omp_rendered

    if HAS_PYLATEXENC:
        l2t = pylatexenc.latex2text.LatexNodes2Text(math_mode="text")
    def _clean_inline(match: re.Match) -> str:
        content = match.group(1).strip()
        if not content:
            return ""
        if HAS_PYLATEXENC:
            try:
                converted = l2t.latex_to_text(content).strip()
                if converted:
                    return converted
            except Exception:
                pass
        c = re.sub(r"\\pm\s*", "±", c)
        c = re.sub(r"\\times\s*", "×", c)
        c = re.sub(r"\\cdot\s*", "·", c)
        c = re.sub(r"\\text\{([^}]*)\}", r"\1", c)
        c = re.sub(r"\{,\}", ",", c)
        c = re.sub(r"\\infty\b", "∞", c)
        c = re.sub(r"\\pi\b", "π", c)
        c = re.sub(r"\\,", " ", c)

        # Sums and integrals with bounds
        c = re.sub(r"\\sum_\{([^}]+)\}\^\{([^}]+)\}", r"∑_{\1}^{\2}", c)
        c = re.sub(r"\\sum_\{([^}]+)\}\^([0-9a-zA-Z∞]+)", r"∑_{\1}^{\2}", c)
        c = re.sub(r"\\sum\b", "∑", c)

        c = re.sub(r"\\int_\{([^}]+)\}\^\{([^}]+)\}", r"∫_{\1}^{\2}", c)
        c = re.sub(r"\\int_([0-9a-zA-Z]+)\^([0-9a-zA-Z\\∞]+)", r"∫_{\1}^{\2}", c)
        c = re.sub(r"\\int_([0-9a-zA-Z]+)\^\{([^}]+)\}", r"∫_{\1}^{\2}", c)
        c = re.sub(r"\\int\b", "∫", c)

        # Roots and fractions
        c = re.sub(r"\\sqrt\{([^{}]+)\}", r"√(\1)", c)
        for _ in range(3):
            c = re.sub(r"\\frac\{([^{}]+)\}\{([^{}]+)\}", r"(\1)/(\2)", c)

        # Subscripts and superscripts
        def _sub(m: re.Match) -> str:
            raw = m.group(1)
            res = raw.translate(SUBSCRIPT_MAP)
            return res if res != raw or raw.isdigit() else f"_{raw}"

        def _sup(m: re.Match) -> str:
            raw = m.group(1)
            res = raw.translate(SUPERSCRIPT_MAP)
            return res if res != raw or raw.isdigit() else f"^{raw}"

        c = re.sub(r"_\{([^}]+)\}", _sub, c)
        c = re.sub(r"_([0-9a-zA-Z=])", lambda m: m.group(1).translate(SUBSCRIPT_MAP), c)
        c = re.sub(r"\^\{([^}]+)\}", _sup, c)
        c = re.sub(r"\^([0-9a-zA-Z=])", lambda m: m.group(1).translate(SUPERSCRIPT_MAP), c)

        c = re.sub(r"\\[a-zA-Z]+", "", c)
        c = re.sub(r"[{}]", "", c)
        return c.strip()

    return re.sub(r"\$([^\$\n]+?)\$", _clean_inline, text)

def render_mixed_markdown_with_math(text: str, console: Console) -> None:
    """
    Renders text by converting LaTeX math (display blocks and inline) to
    beautiful Unicode text using omp's exact renderer (or pylatexenc fallback),
    converting colors to ANSI escapes, and rendering with Rich Markdown.
    """
    # Process color commands (\textcolor, \colorbox)
    text = parse_latex_colors(text)

    # Try omp native renderer first
    omp_rendered = render_math_with_omp(text)
    if omp_rendered != text:
        console.print(Markdown(omp_rendered))
        return

    if HAS_PYLATEXENC:
        l2t = pylatexenc.latex2text.LatexNodes2Text(math_mode="text")

        def _convert_display_math(m: re.Match) -> str:
            raw = m.group(0).strip()
            inner = raw
            if inner.startswith("$$") and inner.endswith("$$"):
                inner = inner[2:-2].strip()
            elif inner.startswith("\\[") and inner.endswith("\\]"):
                inner = inner[2:-2].strip()
            try:
                converted = l2t.latex_to_text(inner).strip()
                if converted:
                    return "\n\n" + converted + "\n\n"
            except Exception:
                pass
            return raw

        text = DISPLAY_MATH_RE.sub(_convert_display_math, text)

    text = sanitize_inline_math(text)
    console.print(Markdown(text))
