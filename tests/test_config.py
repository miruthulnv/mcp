"""Tests for configuration module."""

import pytest

from notes_mcp.config import Settings, get_settings


def test_missing_auth_token_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MCP_AUTH_TOKEN", raising=False)
    with pytest.raises(ValueError, match="MCP_AUTH_TOKEN.*required"):
        get_settings()


def test_empty_auth_token_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MCP_AUTH_TOKEN", "   ")
    with pytest.raises(ValueError, match="MCP_AUTH_TOKEN.*required"):
        get_settings()


def test_default_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MCP_AUTH_TOKEN", "secret-token")
    monkeypatch.delenv("DB_PATH", raising=False)
    monkeypatch.delenv("HOST", raising=False)
    monkeypatch.delenv("PORT", raising=False)
    monkeypatch.delenv("LOG_LEVEL", raising=False)
    monkeypatch.delenv("ALLOWED_HOSTS", raising=False)

    settings = get_settings()
    assert settings.auth_token == "secret-token"
    assert settings.db_path == "data/notes.db"
    assert settings.host == "0.0.0.0"
    assert settings.port == 3000
    assert settings.log_level == "INFO"
    assert settings.allowed_hosts == []


def test_custom_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MCP_AUTH_TOKEN", "my-token")
    monkeypatch.setenv("DB_PATH", "/custom/path.db")
    monkeypatch.setenv("HOST", "127.0.0.1")
    monkeypatch.setenv("PORT", "8080")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("ALLOWED_HOSTS", "mcp.example.com, localhost")

    settings = get_settings()
    assert settings == Settings(
        auth_token="my-token",
        db_path="/custom/path.db",
        host="127.0.0.1",
        port=8080,
        log_level="DEBUG",
        allowed_hosts=["mcp.example.com", "localhost"],
    )


def test_invalid_port_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MCP_AUTH_TOKEN", "my-token")
    monkeypatch.setenv("PORT", "not-a-number")
    with pytest.raises(ValueError, match="PORT.*integer"):
        get_settings()
