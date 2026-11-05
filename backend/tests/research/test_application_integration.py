"""Synthetic application journey including persisted exports, with no external AI."""

from io import BytesIO
from uuid import uuid4

import pytest
from docx import Document
from fastapi.testclient import TestClient
from pypdf import PdfReader

from app.modules.research.dev_app import ResearchDevSettings, create_app
from app.modules.statistics.engine import DeterministicStatisticalEngine
from tests.research.test_analysis_e2e import executed, proposed, research_case


def report_url(case, record, result_id=None, fmt="docx"):
    result_id = result_id or record["result"]["id"]
    return case.root + f"/plans/{record['plan']['id']}/results/{result_id}/report.{fmt}"


@pytest.mark.parametrize("kind", ["descriptive", "association"])
def test_full_preparation_analysis_export_restart(tmp_path, monkeypatch, kind):
    # Helper creates/uploads/extracts a real DOCX, manually reviews/confirms it,
    # uploads a CSV and builds a package through actual HTTP routes.
    case = research_case(tmp_path, kind=kind)
    assert case.client.post(case.dataset + "/eda").status_code == 200
    plan = {"operations": [{"type": "drop_duplicates"}]}
    preview = case.client.post(case.dataset + "/preparation/preview", json=plan)
    assert preview.status_code == 200, preview.text
    preview = preview.json()
    applied = case.client.post(
        case.dataset + "/preparation/apply",
        json={
            "plan": plan,
            "preview_id": preview["preview_id"],
            "plan_hash": preview["plan_hash"],
            "confirm": True,
        },
    )
    assert applied.status_code == 201, applied.text
    derived = applied.json()["result_id"]
    assert case.client.post(case.project + f"/datasets/{derived}/activate").status_code == 200
    assert case.client.post(case.project + f"/datasets/{derived}/eda").status_code == 200
    config = case.client.get(case.package_root + "/configuration").json()
    config["dataset_id"] = derived
    assert case.client.put(case.package_root + "/configuration", json=config).status_code == 200
    case.package = case.client.post(case.package_root + "/build").json()
    _, result = executed(case)
    values = {metric.name: metric.value for metric in result.metrics}
    if kind == "association":
        assert values["n"] == 4
        assert values["r"] == 1
        assert values["p_value"] == 0
    if kind == "descriptive":
        assert values["horas_estudio.mean"] == 2.5
        assert values["rendimiento.mean"] == 5
    case.client = TestClient(create_app(settings=case.settings))
    record = case.client.get(case.root + "/results").json()[0]
    assert record["result"] == result.model_dump(mode="json")

    def cannot_recalculate(*args):
        raise AssertionError("Downloading must never invoke the engine")

    monkeypatch.setattr(DeterministicStatisticalEngine, "execute", cannot_recalculate)
    for fmt in ["docx", "pdf"]:
        response = case.client.get(report_url(case, record, fmt=fmt))
        assert response.status_code == 200, response.text
        assert response.headers["cache-control"] == "no-store"
        assert response.headers["content-disposition"].endswith(f'.{fmt}"')
        if fmt == "docx":
            doc = Document(BytesIO(response.content))
            text = "\n".join(p.text for p in doc.paragraphs)
            text += "\n".join(c.text for t in doc.tables for r in t.rows for c in r.cells)
        else:
            pdf = PdfReader(BytesIO(response.content), strict=True)
            text = "\n".join(page.extract_text() for page in pdf.pages)
        assert result.id in text
        assert derived in text
        assert record["plan"]["technique"] in text
        for metric in result.metrics:
            assert metric.name in text
            assert f"{metric.value:.6g}" in text
        for warning in result.warnings:
            assert " ".join(warning.split()) in " ".join(text.split())
        if kind == "association":
            assert "Dispersión autorizada: horas_estudio y rendimiento" in text
            assert "pares completos; se representan" in text
    assert case.client.get(case.root + "/results").json()[0]["result"] == record["result"]


def test_export_guards_for_missing_foreign_failed_and_stale(tmp_path):
    case = research_case(tmp_path)
    record = proposed(case)
    url = report_url(case, record, "invented")
    assert case.client.get(url).status_code == 404
    _, result = executed(case)
    record = next(item for item in case.client.get(case.root + "/results").json() if item["result"])
    assert case.client.get(report_url(case, record, "wrong")).status_code == 404
    assert case.client.get(report_url(case, record, fmt="html")).status_code == 422
    assert (
        case.client.post(report_url(case, record), json=result.model_dump(mode="json")).status_code
        == 405
    )
    foreign = case.client.post(
        "/api/research/projects",
        json={
            "title": "Otro proyecto ficticio",
            "university": "Demo",
            "program": "Demo",
            "degree": "bachelor",
        },
    ).json()["id"]
    foreign_url = report_url(case, record).replace(
        case.project, f"/api/research/projects/{foreign}"
    )
    assert case.client.get(foreign_url).status_code == 404
    assert (
        case.client.get(
            report_url(case, record).replace(record["plan"]["id"], str(uuid4()))
        ).status_code
        == 404
    )
    config = case.client.get(case.package_root + "/configuration").json()
    config["sampling_notes"] = "Fuente modificada"
    assert case.client.put(case.package_root + "/configuration", json=config).status_code == 200
    assert case.client.get(report_url(case, record)).status_code == 409
    historical = case.client.get(case.root + "/results").json()[-1]
    assert historical["invalidated_at"]
    assert historical["result"] == result.model_dump(mode="json")

    failed = research_case(
        tmp_path / "failed", kind="association", data=b"horas_estudio,rendimiento\n1,2\n1,3\n1,4\n"
    )
    proposal = proposed(failed)
    assert failed.approve(proposal).status_code == 200
    assert failed.execute(proposal).json()["status"] == "failed"
    record = failed.client.get(failed.root + "/results").json()[0]
    assert failed.client.get(report_url(failed, record)).status_code == 409


def test_local_demo_cors_and_environment(tmp_path):
    settings = ResearchDevSettings(
        _env_file=None,
        research_db_path=tmp_path / "local.db",
        research_documents_path=tmp_path / "docs",
        research_datasets_path=tmp_path / "datasets",
    )
    app = create_app(settings=settings)
    client = TestClient(app)
    for origin in ["http://localhost:5173", "http://127.0.0.1:5173"]:
        response = client.options(
            "/api/research/projects",
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "Content-Type,X-File-Name",
            },
        )
        assert response.status_code == 200
        assert response.headers["access-control-allow-origin"] == origin
    assert client.get("/health", headers={"Host": "public.example"}).status_code == 403
    assert (
        TestClient(app, client=("203.0.113.1", 123)).get("/api/research/projects").status_code
        == 403
    )
    with pytest.raises(RuntimeError, match="development"):
        create_app(settings=settings.model_copy(update={"app_env": "production"}))
