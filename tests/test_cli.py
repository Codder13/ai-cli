import re
import sys
from pathlib import Path

import pytest

import ai_cli
from ai_cli import main as cli
from ai_cli.latex_render import has_math, render_math_with_omp, sanitize_inline_math

ROOT = Path(__file__).resolve().parent.parent


class FakeProc:
    def __init__(self, out="output", err="", rc=0):
        self.returncode = rc
        self._out, self._err = out, err

    def communicate(self):
        return self._out, self._err


@pytest.fixture
def fake_pi(monkeypatch):
    """Pretend only `pi` is installed and capture the command that would run."""
    calls = []

    def fake_popen(cmd, **kwargs):
        calls.append(cmd)
        return FakeProc(out="hello $x^2$\n")

    monkeypatch.setattr("shutil.which", lambda name: f"/usr/bin/{name}" if name == "pi" else None)
    monkeypatch.setattr("subprocess.Popen", fake_popen)
    return calls


def run_main(monkeypatch, *argv):
    monkeypatch.setattr(sys, "argv", ["ai", *argv])
    cli.main()


# --- versioning ---------------------------------------------------------------


def test_version_matches_pyproject():
    text = (ROOT / "pyproject.toml").read_text()
    version = re.search(r'^version\s*=\s*"([^"]+)"', text, re.M).group(1)
    assert ai_cli.__version__ == version


def test_version_flag(monkeypatch, capsys):
    with pytest.raises(SystemExit) as exc:
        run_main(monkeypatch, "--version")
    assert exc.value.code == 0
    assert ai_cli.__version__ in capsys.readouterr().out


# --- argument parsing -----------------------------------------------------------


def test_double_dash_stops_option_parsing(monkeypatch, fake_pi, capsys):
    run_main(monkeypatch, "--no-session", "--", "--new", "-m", "x")
    cmd = fake_pi[-1]
    assert cmd[-1] == "--new -m x"
    assert "--model" not in cmd
    assert "--no-session" in cmd


def test_model_and_agent_equals_forms(monkeypatch, fake_pi):
    run_main(monkeypatch, "--agent=pi", "--model=foo", "--no-session", "hi")
    cmd = fake_pi[-1]
    assert cmd[0] == "pi"
    assert cmd[cmd.index("--model") + 1] == "foo"


def test_piped_output_sanitizes_math(monkeypatch, fake_pi, capsys):
    run_main(monkeypatch, "--raw", "--no-session", "hi")
    assert capsys.readouterr().out == "hello x²\n"


def test_harness_failure_propagates_exit_code(monkeypatch, capsys):
    monkeypatch.setattr("shutil.which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr("subprocess.Popen", lambda *a, **k: FakeProc(out="", err="boom\n", rc=3))
    with pytest.raises(SystemExit) as exc:
        run_main(monkeypatch, "-a", "pi", "--raw", "--no-session", "hi")
    assert exc.value.code == 3
    assert "boom" in capsys.readouterr().err


# --- missing harness handling ---------------------------------------------------


def test_no_harness_installed_error(monkeypatch, capsys):
    monkeypatch.setattr("shutil.which", lambda name: None)
    monkeypatch.setattr(sys.stdin, "isatty", lambda: False, raising=False)
    with pytest.raises(SystemExit) as exc:
        run_main(monkeypatch, "--raw", "hi")
    assert exc.value.code == 1
    err = capsys.readouterr().err
    assert "not found in PATH" in err
    assert "No supported harness found" in err


def test_missing_harness_lists_installed(monkeypatch, capsys):
    monkeypatch.setattr("shutil.which", lambda name: "/usr/bin/omp" if name == "omp" else None)
    with pytest.raises(SystemExit):
        run_main(monkeypatch, "-a", "claude", "--raw", "hi")
    assert "Installed harnesses: omp" in capsys.readouterr().err


def test_unknown_env_harness_warns(monkeypatch, capsys):
    monkeypatch.setenv("AI_HARNESS", "nope")
    monkeypatch.setattr("shutil.which", lambda name: "/usr/bin/omp" if name == "omp" else None)
    assert cli.resolve_harness(None) == "omp"
    assert "ignoring unknown AI_HARNESS" in capsys.readouterr().err


def test_config_harness_is_used(monkeypatch):
    cli.save_config({"harness": "codex"})
    assert cli.load_config() == {"harness": "codex"}
    assert cli.resolve_harness(None) == "codex"


# --- sessions -------------------------------------------------------------------


def test_pi_session_auto_resumes_only_when_session_exists(monkeypatch):
    monkeypatch.setattr("ai_cli.main.get_terminal_session_key", lambda: "k")
    first = cli.build_pi_cmd(None, True, "q", session_mode="auto")
    assert "-c" not in first
    session_dir = first[first.index("--session-dir") + 1]
    Path(session_dir, "s.jsonl").write_text("{}\n")
    assert "-c" in cli.build_pi_cmd(None, True, "q", session_mode="auto")
    fresh = cli.build_pi_cmd(None, True, "q", session_mode="new")
    assert "-c" not in fresh
    assert not Path(session_dir, "s.jsonl").exists()


def test_copilot_handoff_has_no_prompt_arg(monkeypatch):
    calls = []
    monkeypatch.setattr("os.execvp", lambda f, a: calls.append(a))
    monkeypatch.setattr("shutil.which", lambda name: f"/usr/bin/{name}")
    cli.execute_handoff("copilot", "do things")
    assert calls[-1] == ["copilot"]


# --- latex rendering ------------------------------------------------------------


@pytest.mark.parametrize(
    ("src", "expected"),
    [
        (r"$\sim 21{,}196\text{ km}$", "~21,196 km"),
        ("area 200 km^2", "area 200 km²"),
        (r"$3 \times 10^{8}$", "3 ×10⁸"),
        ("no math here", "no math here"),
    ],
)
def test_sanitize_inline_math(src, expected):
    assert sanitize_inline_math(src) == expected


def test_has_math():
    assert has_math("$x$")
    assert has_math(r"\[x\]")
    assert not has_math("plain text")


def test_render_math_skips_js_without_math(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("JS renderer should not be spawned")

    monkeypatch.setattr("subprocess.run", boom)
    assert render_math_with_omp("plain text") == "plain text"


def test_cli_import_does_not_load_rich_markdown():
    import subprocess

    code = "import sys, ai_cli.main; print('rich.markdown' in sys.modules, 'pylatexenc' in sys.modules)"
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True)
    assert out.stdout.strip() == "False False"
