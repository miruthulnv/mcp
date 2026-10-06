"""Configuration module for notes-mcp."""

import os
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Settings:
    auth_token: str
    db_path: str = "data/notes.db"
    host: str = "0.0.0.0"
    port: int = 3000
    log_level: str = "INFO"
    allowed_hosts: list[str] = field(default_factory=list)


def get_settings() -> Settings:
    """Build settings from environment variables."""
    token = os.environ.get("MCP_AUTH_TOKEN", "").strip()
    if not token:
        raise ValueError("MCP_AUTH_TOKEN environment variable is required and cannot be empty")

    db_path = os.environ.get("DB_PATH", "data/notes.db").strip() or "data/notes.db"
    host = os.environ.get("HOST", "0.0.0.0").strip() or "0.0.0.0"
    port_str = os.environ.get("PORT", "3000").strip() or "3000"
    try:
        port = int(port_str)
    except ValueError as exc:
        raise ValueError(f"PORT environment variable must be an integer: {port_str}") from exc

    log_level = os.environ.get("LOG_LEVEL", "INFO").strip() or "INFO"

    allowed_hosts_raw = os.environ.get("ALLOWED_HOSTS", "").strip()
    allowed_hosts = [h.strip() for h in allowed_hosts_raw.split(",") if h.strip()]

    return Settings(
        auth_token=token,
        db_path=db_path,
        host=host,
        port=port,
        log_level=log_level,
        allowed_hosts=allowed_hosts,
    )
