import json
import subprocess
import sys
from pathlib import Path

import pytest

from ai_cli import extras
from ai_cli import main as cli


class FakeProc:
    def __init__(self, out="output", err="", rc=0):
        self.returncode = rc
        self._out, self._err = out, err

    def communicate(self):
        return self._out, self._err


@pytest.fixture
def harness(monkeypatch):
    """Only `pi` installed; every call returns `state['out']`. Captures commands."""
    state = {"out": "answer\n", "calls": []}

    def fake_run(cmd):
        state["calls"].append(cmd)
        return state["out"], ""

    real_which = __import__("shutil").which
    monkeypatch.setattr(
        "shutil.which", lambda name: f"/usr/bin/{name}" if name == "pi" else real_which(name) if name == "git" else None
    )
    monkeypatch.setattr(cli, "_run_harness", fake_run)
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True, raising=False)
    monkeypatch.setenv("AI_NO_FOOTER", "1")
    return state


def run(monkeypatch, *argv):
    monkeypatch.setattr(sys, "argv", ["ai", *argv])
    cli.main()


def prompt_of(state):
    return state["calls"][-1][-1]


# --- 1. --json ---------------------------------------------------------------------


def test_json_output(monkeypatch, harness, capsys):
    harness["out"] = "Use this:\n```bash\nls -la\n```\n"
    run(monkeypatch, "--json", "--no-session", "list files")
    data = json.loads(capsys.readouterr().out)
    assert data["harness"] == "pi"
    assert data["code"] == "ls -la"
    assert "ls -la" in data["response"]
    assert isinstance(data["seconds"], float)


# --- 2. --copy ---------------------------------------------------------------------


def test_copy_prefers_code_block(monkeypatch, harness, capsys):
    copied = []
    monkeypatch.setattr(extras, "copy_to_clipboard", lambda t: copied.append(t) or "wl-copy")
    harness["out"] = "Try\n```\nrg foo\n```\n"
    run(monkeypatch, "-c", "--raw", "--no-session", "search")
    assert copied == ["rg foo"]
    assert "copied code block" in capsys.readouterr().err


def test_copy_whole_answer_without_code(monkeypatch, harness):
    copied = []
    monkeypatch.setattr(extras, "copy_to_clipboard", lambda t: copied.append(t) or "wl-copy")
    harness["out"] = "just text\n"
    run(monkeypatch, "--copy", "--raw", "--no-session", "q")
    assert copied == ["just text"]


# --- 3. -f globs ----------------------------------------------------------------------


def test_file_globs_are_added(monkeypatch, harness, tmp_path):
    (tmp_path / "a.py").write_text("print('A')\n")
    (tmp_path / "b.py").write_text("print('B')\n")
    (tmp_path / "bin.dat").write_bytes(b"\0\1\2")
    monkeypatch.chdir(tmp_path)
    run(monkeypatch, "-f", "*.py", "-f", "*.dat", "--raw", "--no-session", "--no-context", "review")
    p = prompt_of(harness)
    assert "### a.py" in p and "print('B')" in p
    assert "bin.dat" not in p.split("## Files", 1)[1].split("review")[0] or "\0" not in p
    assert p.rstrip().endswith("review")


def test_file_glob_without_prompt(monkeypatch, harness, tmp_path):
    (tmp_path / "x.txt").write_text("hello")
    monkeypatch.chdir(tmp_path)
    run(monkeypatch, "--file=x.txt", "--raw", "--no-session", "--no-context")
    assert "hello" in prompt_of(harness)


def test_missing_glob_warns(tmp_path):
    block, warnings = extras.expand_file_args([str(tmp_path / "nope*.py")])
    assert block == "" and "no files match" in warnings[0]


# --- 4. per-dir context --------------------------------------------------------------


def test_project_and_global_context(monkeypatch, harness, tmp_path, isolated_dirs):
    proj = tmp_path / "proj" / "sub"
    proj.mkdir(parents=True)
    (tmp_path / "proj" / ".ai.md").write_text("Use Luau strict mode.")
    cfg = isolated_dirs / "config"
    cfg.mkdir(parents=True, exist_ok=True)
    (cfg / "context.md").write_text("I use Arch + niri.")
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.chdir(proj)
    run(monkeypatch, "--raw", "--no-session", "hi")
    p = prompt_of(harness)
    assert "Use Luau strict mode." in p and "I use Arch + niri." in p
    run(monkeypatch, "--raw", "--no-session", "--no-context", "hi")
    assert prompt_of(harness).strip() == "hi"


def test_context_stops_at_home(monkeypatch, tmp_path):
    (tmp_path / ".ai.md").write_text("outside")
    home = tmp_path / "home"
    (home / "p").mkdir(parents=True)
    monkeypatch.setattr(Path, "home", lambda: home)
    assert extras.find_project_context(home / "p") is None


# --- 5. explain ------------------------------------------------------------------------


def test_explain_wraps_piped_output(monkeypatch, harness):
    monkeypatch.setattr(cli, "_read_stdin", lambda: "error: E0382 borrow of moved value")
    run(monkeypatch, "explain", "--raw", "--no-context")
    p = prompt_of(harness)
    assert "what went wrong" in p and "E0382" in p


def test_explain_without_input_errors(monkeypatch, harness):
    monkeypatch.setattr(cli, "_read_stdin", lambda: "")
    with pytest.raises(SystemExit) as e:
        run(monkeypatch, "explain")
    assert e.value.code == 2


# --- 6. do ------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "cmd"),
    [
        ("ls -la\n", "ls -la"),
        ("```bash\nfind . -size +100M\n```", "find . -size +100M"),
        ("`du -sh *`", "du -sh *"),
        ("$ echo hi", "echo hi"),
        ("```sh\ncd /tmp\nls\n```", "cd /tmp && ls"),
    ],
)
def test_clean_single_command(raw, cmd):
    assert extras.clean_single_command(raw) == cmd


def test_do_print_mode(monkeypatch, harness, capsys):
    harness["out"] = "```bash\nfind ~ -size +100M\n```"
    run(monkeypatch, "do", "--print", "big", "files")
    assert capsys.readouterr().out.strip() == "find ~ -size +100M"
    cmd = harness["calls"][-1]
    assert "--no-tools" in cmd and "--no-session" in cmd
    assert "big files" in cmd[-1]


def test_do_confirm_runs(monkeypatch, harness):
    harness["out"] = "echo ok"
    ran = []
    monkeypatch.setattr(extras, "ask_choice", lambda q, default="y": "y")
    monkeypatch.setattr(cli, "_append_shell_history", lambda c: None)
    monkeypatch.setattr("subprocess.call", lambda c, **k: ran.append(c) or 0)
    monkeypatch.setattr("os.isatty", lambda fd: True)
    with pytest.raises(SystemExit) as e:
        run(monkeypatch, "do", "--raw", "say ok")
    assert e.value.code == 0 and ran == ["echo ok"]


def test_do_decline(monkeypatch, harness):
    harness["out"] = "rm -rf /tmp/x"
    monkeypatch.setattr(extras, "ask_choice", lambda q, default="y": "n")
    monkeypatch.setattr("os.isatty", lambda fd: True)
    monkeypatch.setattr("subprocess.call", lambda *a, **k: pytest.fail("must not run"))
    with pytest.raises(SystemExit) as e:
        run(monkeypatch, "do", "--raw", "clean tmp")
    assert e.value.code == 1


def test_do_you_know_is_a_question(monkeypatch, harness, capsys):
    run(monkeypatch, "do", "you", "know", "rust?", "--raw", "--no-session", "--no-context")
    assert prompt_of(harness) == "do you know rust?"


# --- 7. commit --------------------------------------------------------------------------


@pytest.fixture
def repo(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    g = lambda *a: subprocess.run(["git", *a], check=True, capture_output=True)  # noqa: E731
    g("init", "-q")
    g("config", "user.email", "t@t")
    g("config", "user.name", "t")
    (tmp_path / "f.txt").write_text("one\n")
    g("add", ".")
    g("commit", "-qm", "feat: initial")
    return g


def test_commit_nothing_staged(monkeypatch, harness, repo):
    with pytest.raises(SystemExit) as e:
        run(monkeypatch, "commit")
    assert e.value.code == 1


def test_commit_print(monkeypatch, harness, repo, tmp_path, capsys):
    (tmp_path / "f.txt").write_text("two\n")
    repo("add", ".")
    harness["out"] = "```\nfix(f): change one to two\n```"
    run(monkeypatch, "commit", "--print", "--no-context")
    assert capsys.readouterr().out.strip() == "fix(f): change one to two"
    p = prompt_of(harness)
    assert "+two" in p and "feat: initial" in p


def test_commit_confirm_commits(monkeypatch, harness, repo, tmp_path):
    (tmp_path / "f.txt").write_text("three\n")
    repo("add", ".")
    harness["out"] = "chore: three"
    monkeypatch.setattr(extras, "ask_choice", lambda q, default="y": "y")
    with pytest.raises(SystemExit) as e:
        run(monkeypatch, "commit", "--raw", "--no-context")
    assert e.value.code == 0
    log = subprocess.run(["git", "log", "-1", "--pretty=%s"], capture_output=True, text=True).stdout.strip()
    assert log == "chore: three"


# --- 8. log -----------------------------------------------------------------------------


def _session(cache: Path, harness_name: str, key: str, turns: list[tuple[str, str]]):
    d = cache / harness_name / key
    d.mkdir(parents=True)
    with open(d / "s.jsonl", "w") as f:
        for role, text in turns:
            f.write(json.dumps({"type": "message", "message": {"role": role, "content": text}}) + "\n")


def test_log_lists_and_filters(monkeypatch, harness, isolated_dirs, capsys):
    cache = isolated_dirs / "cache" / "sessions"
    _session(cache, "pi", "k1", [("user", "how to use rojo sync"), ("assistant", "run rojo serve")])
    _session(cache, "omp", "k2", [("user", "tar extract"), ("assistant", "tar xzf")])
    monkeypatch.setattr(sys.stdout, "isatty", lambda: False)
    run(monkeypatch, "log")
    out = capsys.readouterr().out
    assert "rojo sync" in out and "tar extract" in out
    run(monkeypatch, "log", "serve")
    out = capsys.readouterr().out
    assert "rojo sync" in out and "tar extract" not in out
    run(monkeypatch, "log", "--json")
    assert {s["harness"] for s in json.loads(capsys.readouterr().out)} == {"pi", "omp"}


def test_log_empty(monkeypatch, harness):
    with pytest.raises(SystemExit) as e:
        run(monkeypatch, "log", "nothing")
    assert e.value.code == 1


# --- 9. footer ---------------------------------------------------------------------------


def test_footer_on_stderr_tty(monkeypatch, harness, capsys):
    monkeypatch.delenv("AI_NO_FOOTER")
    monkeypatch.setattr(sys.stderr, "isatty", lambda: True)
    run(monkeypatch, "--raw", "--no-session", "-m", "gpt-x", "q")
    err = capsys.readouterr().err
    assert "pi · gpt-x ·" in err and err.rstrip().endswith("s\x1b[0m")


def test_no_footer_when_piped(monkeypatch, harness, capsys):
    monkeypatch.delenv("AI_NO_FOOTER")
    monkeypatch.setattr(sys.stderr, "isatty", lambda: False)
    run(monkeypatch, "--raw", "--no-session", "q")
    assert capsys.readouterr().err == ""


# --- 10. zsh widget ------------------------------------------------------------------------


def test_zsh_snippet(monkeypatch, capsys):
    with pytest.raises(SystemExit):
        run(monkeypatch, "--zsh")
    out = capsys.readouterr().out
    assert "zle -N _ai_flow_widget" in out and "ai do --print" in out


def test_zsh_snippet_is_valid_zsh(monkeypatch):
    import shutil

    if not shutil.which("zsh"):
        pytest.skip("zsh not installed")
    r = subprocess.run(["zsh", "-n"], input=extras.ZSH_SNIPPET, text=True, capture_output=True)
    assert r.returncode == 0, r.stderr


# --- regressions ------------------------------------------------------------------------


def test_help_mentions_new_commands(monkeypatch, capsys):
    with pytest.raises(SystemExit):
        run(monkeypatch, "--help")
    out = capsys.readouterr().out
    for word in ("ai do", "ai commit", "ai explain", "ai log", "--copy", "--json", "--file", "--zsh", ".ai.md"):
        assert word in out


def test_import_stays_light():
    code = "import sys, ai_cli.main; print('ai_cli.extras' in sys.modules, 'rich.markdown' in sys.modules)"
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True)
    assert out.stdout.strip() == "False False"


@pytest.mark.parametrize("sub", ["do", "commit", "explain", "log"])
def test_subcommand_help(monkeypatch, capsys, sub):
    with pytest.raises(SystemExit) as e:
        run(monkeypatch, sub, "--help")
    assert e.value.code == 0
    out = capsys.readouterr().out
    assert out.startswith(f"ai {sub}") and "Examples:" in out


def test_help_topic_and_every_flag_has_example(monkeypatch, capsys):
    with pytest.raises(SystemExit):
        run(monkeypatch, "help", "do")
    assert "Run it? [Y/e/n]" in capsys.readouterr().out
    with pytest.raises(SystemExit):
        run(monkeypatch, "--help")
    out = capsys.readouterr().out
    for flag in ("-f 'src", "ai -c ", "--json \"", "ai -H omp", "ai do find", "ai commit", "| ai explain", "ai log rojo", "--zsh"):
        assert flag in out, flag
