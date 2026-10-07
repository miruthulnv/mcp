"""Tests for bearer authentication and HTTP application endpoints."""

from pathlib import Path

import pytest
from starlette.testclient import TestClient

from notes_mcp.config import Settings
from notes_mcp.main import create_app


@pytest.fixture
def auth_client(tmp_path: Path):
    settings = Settings(
        auth_token="test-secret-token",
        db_path=str(tmp_path / "notes_auth.db"),
        allowed_hosts=["*"],
    )
    application = create_app(settings)
    with TestClient(application) as client:
        yield client


def test_health_returns_200_without_token(auth_client: TestClient) -> None:
    response = auth_client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_mcp_returns_401_without_token(auth_client: TestClient) -> None:
    response = auth_client.get("/mcp")
    assert response.status_code == 401
    assert response.headers.get("www-authenticate") == "Bearer"
    assert response.json() == {"error": "Unauthorized"}


def test_mcp_returns_401_with_wrong_token(auth_client: TestClient) -> None:
    response = auth_client.get("/mcp", headers={"Authorization": "Bearer wrong-token"})
    assert response.status_code == 401
    assert response.headers.get("www-authenticate") == "Bearer"
    assert response.json() == {"error": "Unauthorized"}


def test_mcp_with_correct_token_is_not_rejected_by_auth(auth_client: TestClient) -> None:
    # A request with the correct token passes auth middleware and reaches the MCP handler
    response = auth_client.get("/mcp", headers={"Authorization": "Bearer test-secret-token"})
    assert response.status_code != 401
