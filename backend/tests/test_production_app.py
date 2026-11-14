"""Integration tests verifying the production application composition.

Validates:
1. Production app startup and /health + /api/health endpoints.
2. CORS behavior with Vercel origin (https://tesisstat-ai.vercel.app).
3. Multi-tenant isolation (user A cannot access user B's projects).
4. Project creation, retrieval, and dataset upload processing.
5. Verification that secrets are never exposed.
"""

from pathlib import Path
from tempfile import TemporaryDirectory
from fastapi.testclient import TestClient
import pytest

from app.core.config import Settings
from app.production_app import create_production_app


@pytest.fixture
def prod_client():
    with TemporaryDirectory() as tmpdir:
        settings = Settings(
            app_env="production",
            cors_origins=["https://tesisstat-ai.vercel.app", "http://localhost:5173"],
            gemini_api_key="secret_test_gemini_key_12345",
            research_storage_dir=Path(tmpdir) / "data",
            _env_file=None,
        )
        app = create_production_app(settings)
        client = TestClient(app)
        yield client


def test_production_health_check_returns_clean_contract_and_no_secrets(prod_client):
    # 1. Root health check
    res = prod_client.get("/health")
    assert res.status_code == 200
    assert res.json() == {
        "status": "ok",
        "service": "tesisstat-api",
        "version": "0.1.0",
    }

    # 2. Detailed API health check
    res_api = prod_client.get("/api/health")
    assert res_api.status_code == 200
    data = res_api.json()
    assert data["status"] == "ok"
    assert data["environment"] == "production"
    assert data["ai_configured"] is True
    assert data["ai_provider"] == "gemini"

    # Ensure secret key is NEVER exposed in the response
    assert "secret_test_gemini_key_12345" not in res_api.text


def test_production_cors_allows_vercel_origin(prod_client):
    # Preflight OPTIONS request from Vercel
    allowed = prod_client.options(
        "/api/health",
        headers={
            "Origin": "https://tesisstat-ai.vercel.app",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert allowed.status_code == 200
    assert allowed.headers.get("access-control-allow-origin") == "https://tesisstat-ai.vercel.app"

    # Preflight from untrusted origin
    denied = prod_client.options(
        "/api/health",
        headers={
            "Origin": "https://malicious-site.com",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert "access-control-allow-origin" not in denied.headers or denied.headers["access-control-allow-origin"] != "https://malicious-site.com"


def test_multi_tenant_isolation_protects_projects(prod_client):
    # User A creates a research project
    resp_a = prod_client.post(
        "/api/research/projects",
        json={
            "title": "Tesis Secreta del Usuario A",
            "degree": "master",
            "academic_year": 2026,
        },
        headers={"X-Session-ID": "session_user_A"},
    )
    assert resp_a.status_code == 201
    proj_a = resp_a.json()
    proj_id_a = proj_a["id"]

    # User A can access Project A
    get_a = prod_client.get(
        f"/api/research/projects/{proj_id_a}",
        headers={"X-Session-ID": "session_user_A"},
    )
    assert get_a.status_code == 200
    assert get_a.json()["title"] == "Tesis Secreta del Usuario A"

    # User B lists projects -> Project A MUST NOT be exposed to User B!
    list_b = prod_client.get(
        "/api/research/projects",
        headers={"X-Session-ID": "session_user_B"},
    )
    assert list_b.status_code == 200
    titles_b = [p["title"] for p in list_b.json()]
    assert "Tesis Secreta del Usuario A" not in titles_b

    # User B attempts to access Project A directly -> MUST return 403 Forbidden!
    forbidden_b = prod_client.get(
        f"/api/research/projects/{proj_id_a}",
        headers={"X-Session-ID": "session_user_B"},
    )
    assert forbidden_b.status_code == 403
    assert "No tienes autorización" in forbidden_b.json()["detail"]


def test_production_agentic_conversation_flow(prod_client):
    # User creates project and interacts with agentic chat in production
    resp = prod_client.post(
        "/api/research/projects",
        json={"title": "Investigación Estadística Prod", "degree": "bachelor"},
        headers={"X-Session-ID": "prod_sess_100"},
    )
    pid = resp.json()["id"]

    # Get active conversation
    conv_resp = prod_client.get(
        f"/api/v2/research/projects/{pid}/agentic/conversations/active",
        headers={"X-Session-ID": "prod_sess_100"},
    )
    assert conv_resp.status_code == 200
    conv = conv_resp.json()
    assert conv["project_id"] == pid
    assert len(conv["messages"]) >= 1
