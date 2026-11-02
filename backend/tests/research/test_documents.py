import io
import zipfile
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.modules.research.dev_app import ResearchDevSettings, create_app
from app.modules.research.documents.use_cases import MAX_DOCUMENT_BYTES

PROJECT = {
    "title": "Investigación ficticia documental",
    "university": "Universidad de Demostración",
    "program": "Programa sintético",
    "degree": "bachelor",
}
PDF = b"%PDF-1.4\n1 0 obj <</Type /Catalog>> endobj\n%%EOF\n"


def docx() -> bytes:
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr("word/document.xml", "<document/>")
    return stream.getvalue()


def client(tmp_path):
    settings = ResearchDevSettings(
        research_db_path=tmp_path / "projects.sqlite3",
        research_documents_path=tmp_path / "documents",
    )
    return TestClient(create_app(settings=settings)), settings


def upload(client, project_id, name, data):
    return client.post(
        f"/api/research/projects/{project_id}/documents",
        content=data,
        headers={"X-File-Name": name, "Content-Type": "application/octet-stream"},
    )


def test_valid_upload_list_restart_and_delete(tmp_path):
    app, settings = client(tmp_path)
    project = app.post("/api/research/projects", json=PROJECT).json()
    project_id = project["id"]
    first = upload(app, project_id, "fixture.pdf", PDF)
    second = upload(app, project_id, "fixture.docx", docx())
    assert first.status_code == second.status_code == 201
    assert first.json()["format"] == "pdf"
    assert second.json()["format"] == "docx"
    assert first.json()["size"] == len(PDF)
    assert first.json()["uploaded_at"]
    assert sorted(path.name for path in settings.research_documents_path.iterdir()) == sorted(
        [first.json()["id"].replace("-", ""), second.json()["id"].replace("-", "")]
    )
    restarted = TestClient(create_app(settings=settings))
    listing = restarted.get(f"/api/research/projects/{project_id}/documents")
    assert listing.status_code == 200
    assert {item["id"] for item in listing.json()} == {first.json()["id"], second.json()["id"]}
    removed = restarted.delete(
        f"/api/research/projects/{project_id}/documents/{first.json()['id']}"
    )
    assert removed.status_code == 204
    assert not (settings.research_documents_path / first.json()["id"].replace("-", "")).exists()
    assert (
        restarted.delete(
            f"/api/research/projects/{project_id}/documents/{first.json()['id']}"
        ).status_code
        == 404
    )
    assert restarted.delete(f"/api/research/projects/{project_id}").status_code == 204
    assert list(settings.research_documents_path.iterdir()) == []


@pytest.mark.parametrize(
    ("name", "data"),
    [
        ("bad.txt", PDF),
        ("bad.pdf", b"not a PDF"),
        ("bad.docx", b"PK invalid"),
        ("empty.pdf", b""),
        ("large.pdf", b"%PDF-" + b"x" * MAX_DOCUMENT_BYTES),
    ],
)
def test_rejects_invalid_files(tmp_path, name, data):
    app, settings = client(tmp_path)
    project_id = app.post("/api/research/projects", json=PROJECT).json()["id"]
    assert upload(app, project_id, name, data).status_code == 422
    assert app.get(f"/api/research/projects/{project_id}/documents").json() == []
    assert list(settings.research_documents_path.iterdir()) == []


def test_missing_project_and_document(tmp_path):
    app, _ = client(tmp_path)
    missing = uuid4()
    assert upload(app, missing, "fixture.pdf", PDF).status_code == 404
    assert app.get(f"/api/research/projects/{missing}/documents").status_code == 404
    assert app.delete(f"/api/research/projects/{missing}/documents/{uuid4()}").status_code == 404


def test_client_path_is_only_display_name(tmp_path):
    app, settings = client(tmp_path)
    project_id = app.post("/api/research/projects", json=PROJECT).json()["id"]
    response = upload(app, project_id, "..%2F..%2Fescape.pdf", PDF)
    assert response.status_code == 201
    assert response.json()["name"] == "escape.pdf"
    assert [path.name for path in settings.research_documents_path.iterdir()] == [
        response.json()["id"].replace("-", "")
    ]


def test_storage_failure_preserves_metadata(tmp_path):
    app, settings = client(tmp_path)
    project_id = app.post("/api/research/projects", json=PROJECT).json()["id"]
    created = upload(app, project_id, "fixture.pdf", PDF).json()
    path = settings.research_documents_path / created["id"].replace("-", "")
    path.unlink()
    response = app.delete(f"/api/research/projects/{project_id}/documents/{created['id']}")
    assert response.status_code == 503
    assert len(app.get(f"/api/research/projects/{project_id}/documents").json()) == 1
