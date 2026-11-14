from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


def test_health_without_credentials():
    client = TestClient(create_app(Settings(_env_file=None)))
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "tesisstat-api",
        "version": "0.1.0",
    }


def test_cors_respects_configured_origins():
    client = TestClient(
        create_app(Settings(_env_file=None, cors_origins=["http://localhost:5173"]))
    )
    allowed = client.options(
        "/health",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert allowed.headers["access-control-allow-origin"] == "http://localhost:5173"
    denied = client.options(
        "/health",
        headers={
            "Origin": "https://untrusted.example",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert denied.status_code == 400
    assert "access-control-allow-origin" not in denied.headers


def test_settings_load_cors_json_from_environment(monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", '["http://127.0.0.1:5173"]')
    assert Settings(_env_file=None).cors_origins == ["http://127.0.0.1:5173"]
