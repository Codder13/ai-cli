import pytest


@pytest.fixture(autouse=True)
def isolated_dirs(monkeypatch, tmp_path):
    """Never touch the real ~/.cache/ai or ~/.config/ai during tests."""
    monkeypatch.setattr("ai_cli.main.CACHE_DIR", tmp_path / "cache" / "sessions")
    monkeypatch.setattr("ai_cli.main.CONFIG_DIR", tmp_path / "config")
    monkeypatch.setattr("ai_cli.main.CONFIG_FILE", tmp_path / "config" / "config.json")
    monkeypatch.delenv("AI_HARNESS", raising=False)
    return tmp_path
