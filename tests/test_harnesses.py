import os

import pytest

from ai_cli.main import (
    HARNESS_REGISTRY,
    build_claude_cmd,
    build_codex_cmd,
    build_copilot_cmd,
    build_omp_cmd,
    build_pi_cmd,
    clear_terminal_session,
    detect_installed_harnesses,
    execute_handoff,
    format_session_for_handoff,
    get_terminal_session_dir,
    get_terminal_session_key,
    load_terminal_session_history,
    resolve_harness,
)


def test_registry_contains_popular_harnesses():
    expected = {"pi", "omp", "claude", "codex", "copilot", "opencode"}
    assert expected.issubset(set(HARNESS_REGISTRY.keys()))

def test_build_pi_cmd():
    cmd = build_pi_cmd(model=None, enable_tools=False, prompt="hello world", session_mode="none")
    assert cmd[0] == "pi"
    assert "-p" in cmd
    assert "--no-session" in cmd
    assert "--no-tools" in cmd
    assert cmd[-1] == "hello world"

    cmd_auto = build_pi_cmd(model=None, enable_tools=False, prompt="hello world", session_mode="auto")
    assert "--session-dir" in cmd_auto

    cmd_tools = build_pi_cmd(model="my-model", enable_tools=True, prompt="test")
    assert "--no-tools" not in cmd_tools
    assert "--model" in cmd_tools
    assert "my-model" in cmd_tools

def test_build_omp_cmd():
    cmd = build_omp_cmd(model=None, enable_tools=False, prompt="hello", session_mode="none")
    assert cmd[0] == "omp"
    assert "--no-tools" in cmd
    assert "--no-session" in cmd

    cmd_tools = build_omp_cmd(model=None, enable_tools=True, prompt="hello")
    assert "--auto-approve" in cmd_tools
    assert "--session-dir" in cmd_tools

def test_build_claude_cmd():
    cmd = build_claude_cmd(model=None, enable_tools=False, prompt="hello", session_mode="none")
    assert cmd[0] == "claude"
    assert "-p" in cmd
    assert "--no-session-persistence" in cmd
    assert "--tools" in cmd
    idx = cmd.index("--tools")
    assert cmd[idx + 1] == ""

def test_build_copilot_cmd():
    cmd = build_copilot_cmd(model=None, enable_tools=True, prompt="hello", session_mode="auto")
    assert "--allow-all" in cmd
    assert "--available-tools" not in cmd

    cmd_no_tools = build_copilot_cmd(model=None, enable_tools=False, prompt="hello", session_mode="none")
    assert "--allow-all" not in cmd_no_tools
    assert "--available-tools" in cmd_no_tools

def test_build_codex_cmd():
    cmd = build_codex_cmd(model="o3", enable_tools=True, prompt="task", session_mode="none")
    assert "--ephemeral" in cmd
    assert "--dangerously-bypass-approvals-and-sandbox" in cmd
    assert "-m" in cmd
def test_main_cli_tool_flags(monkeypatch):
    import sys
    captured = {}
    def fake_build_pi_cmd(model, enable_tools, prompt, session_mode):
        captured["enable_tools"] = enable_tools
        return ["pi", "-p", prompt]
    monkeypatch.setattr("shutil.which", lambda cmd: "/usr/bin/" + cmd)
    monkeypatch.setitem(HARNESS_REGISTRY["pi"], "builder", fake_build_pi_cmd)
    monkeypatch.setattr("ai_cli.main.resolve_harness", lambda cli_harness=None, console=None: "pi")
    class FakeProc:
        returncode = 0
        def communicate(self):
            return ("output", "")
    monkeypatch.setattr("subprocess.Popen", lambda *args, **kwargs: FakeProc())
    # Test default: enable_tools is True
    monkeypatch.setattr(sys, "argv", ["ai", "--no-session", "test prompt"])
    from ai_cli.main import main
    main()
    assert captured["enable_tools"] is True

    # Test --no-tools: enable_tools is False
    monkeypatch.setattr(sys, "argv", ["ai", "--no-tools", "--no-session", "test prompt"])
    main()
    assert captured["enable_tools"] is False

    # Test -nt alias: enable_tools is False
    monkeypatch.setattr(sys, "argv", ["ai", "-nt", "--no-session", "test prompt"])
    main()
    assert captured["enable_tools"] is False

    # Test --tools overrides
    monkeypatch.setattr(sys, "argv", ["ai", "--tools", "--no-session", "test prompt"])
    main()
    assert captured["enable_tools"] is True

def test_resolve_harness_cli_override():
    assert resolve_harness(cli_harness="omp") == "omp"
    assert resolve_harness(cli_harness="claude") == "claude"

def test_resolve_harness_invalid():
    with pytest.raises(SystemExit):
        resolve_harness(cli_harness="nonexistent-tool")

def test_detect_installed_harnesses(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda name: f"/fake/bin/{name}" if name in ("pi", "claude") else None)
    detected = detect_installed_harnesses()
    assert detected == ["pi", "claude"]

def test_terminal_session_key():
    key = get_terminal_session_key()
    assert key is not None
    assert len(key) > 0

def test_terminal_session_dir_and_clear():
    session_dir = get_terminal_session_dir("test_harness")
    assert os.path.isdir(session_dir)
    # Write a dummy session file
    test_file = os.path.join(session_dir, "test.jsonl")
    with open(test_file, "w") as f:
        f.write("hello")
    assert os.path.exists(test_file)

    clear_terminal_session()
    assert not os.path.exists(session_dir)

def test_format_session_for_handoff(monkeypatch, tmp_path):
    dummy_cache = tmp_path / "sessions"
    dummy_cache.mkdir()
    pi_dir = dummy_cache / "pi" / "dummy_key"
    pi_dir.mkdir(parents=True)
    jsonl_file = pi_dir / "session.jsonl"
    import json
    with open(jsonl_file, "w") as f:
        f.write(json.dumps({"type": "message", "message": {"role": "user", "content": [{"type": "text", "text": "hello from user"}]}}) + "\n")
        f.write(json.dumps({"type": "message", "message": {"role": "assistant", "content": "hello from assistant"}}) + "\n")

    monkeypatch.setattr("ai_cli.main.CACHE_DIR", dummy_cache)
    monkeypatch.setattr("ai_cli.main.get_terminal_session_key", lambda: "dummy_key")

    history = load_terminal_session_history()
    assert len(history) == 2
    assert history[0]["role"] == "user"
    assert history[0]["content"] == "hello from user"
    assert history[1]["role"] == "assistant"
    assert history[1]["content"] == "hello from assistant"

    formatted = format_session_for_handoff()
    assert "Prior Conversation Context" in formatted
    assert "hello from user" in formatted
    assert "hello from assistant" in formatted

def test_execute_handoff_command_formation(monkeypatch):
    executed_args = []
    def fake_execvp(file, args):
        executed_args.append((file, args))
    monkeypatch.setattr("os.execvp", fake_execvp)
    monkeypatch.setattr("shutil.which", lambda name: f"/fake/bin/{name}")
    monkeypatch.setattr("ai_cli.main.load_terminal_session_history", lambda: [{"role": "user", "content": "previous question"}])

    execute_handoff("omp", "my extra instruction")

    file, args = executed_args[0]
    assert file == "omp"
    assert "my extra instruction" in args[-1]
    assert "previous question" in args[-1]

    execute_handoff("claude", "")

    file, args = executed_args[1]
    assert file == "claude"
    assert "previous question" in args[-1]

