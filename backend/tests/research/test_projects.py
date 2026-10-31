import sqlite3
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.modules.research.dev_app import ResearchDevSettings, create_app
from app.modules.research.projects.models import Project, ProjectDraft
from app.modules.research.projects.sqlite_repository import SQLiteProjectRepository
from app.modules.research.projects.use_cases import ProjectNotFound, ProjectService

PAYLOAD = {
    "title": "Investigación completamente ficticia",
    "description": "Ejemplo sintético para pruebas.",
    "university": "Universidad de Demostración",
    "faculty": "Facultad simulada",
    "program": "Programa ficticio",
    "degree": "bachelor",
    "academic_year": 2026,
}
URL = "/api/research/projects"


class MemoryRepository:
    """A separate implementation proves use cases don't depend on SQLite."""

    def __init__(self):
        self.projects: dict = {}

    def list(self):
        return list(self.projects.values())

    def get(self, project_id):
        return self.projects.get(project_id)

    def add(self, project):
        self.projects[project.id] = project

    def replace(self, project):
        if project.id not in self.projects:
            return False
        self.projects[project.id] = project
        return True

    def delete(self, project_id):
        return self.projects.pop(project_id, None) is not None


def test_use_cases_work_with_an_interchangeable_repository():
    service = ProjectService(MemoryRepository())
    assert service.list() == []
    project = service.create(ProjectDraft(**PAYLOAD))
    assert project.status == "draft"
    assert project.created_at == project.updated_at
    assert service.get(project.id) == project
    edited = service.update(project.id, ProjectDraft(**(PAYLOAD | {"title": "Título modificado"})))
    assert edited.id == project.id
    assert edited.created_at == project.created_at
    assert edited.updated_at >= project.updated_at
    assert service.list() == [edited]
    service.delete(project.id)
    assert service.list() == []


def test_use_cases_report_missing_projects():
    service = ProjectService(MemoryRepository())
    missing = uuid4()
    for action in (
        lambda: service.get(missing),
        lambda: service.update(missing, ProjectDraft(**PAYLOAD)),
        lambda: service.delete(missing),
    ):
        with pytest.raises(ProjectNotFound):
            action()


def test_update_handles_concurrent_deletion():
    repository = MemoryRepository()
    service = ProjectService(repository)
    project = service.create(ProjectDraft(**PAYLOAD))
    repository.replace = lambda project: False
    with pytest.raises(ProjectNotFound):
        service.update(project.id, ProjectDraft(**PAYLOAD))


def test_sqlite_persists_across_repository_instances(tmp_path):
    path = tmp_path / "projects.sqlite3"
    first = ProjectService(SQLiteProjectRepository(path))
    project = first.create(ProjectDraft(**PAYLOAD))
    second = ProjectService(SQLiteProjectRepository(path))
    assert second.get(project.id) == project
    edited = second.update(project.id, ProjectDraft(**(PAYLOAD | {"title": "Edición persistente"})))
    assert first.get(project.id) == edited
    second.delete(project.id)
    assert first.list() == []


@pytest.fixture
def client(tmp_path):
    settings = ResearchDevSettings(
        _env_file=None,
        research_db_path=tmp_path / "api.sqlite3",
        cors_origins=["http://localhost:5174"],
    )
    with TestClient(create_app(settings=settings)) as client:
        yield client


def test_api_full_crud(client):
    assert client.get(URL).json() == []
    created = client.post(URL, json=PAYLOAD)
    assert created.status_code == 201
    project = Project.model_validate(created.json())
    location = f"{URL}/{project.id}"
    assert created.headers["location"] == location
    assert client.get(location).json() == created.json()
    assert len(client.get(URL).json()) == 1
    updated = client.put(location, json=PAYLOAD | {"title": "Nuevo título simulado"})
    assert updated.status_code == 200
    assert updated.json()["title"] == "Nuevo título simulado"
    assert updated.json()["created_at"] == created.json()["created_at"]
    assert client.get(location).json() == updated.json()
    assert client.delete(location).status_code == 204
    assert client.get(URL).json() == []
    assert client.get(location).status_code == 404
    assert client.delete(location).status_code == 404
    assert client.put(location, json=PAYLOAD).status_code == 404


@pytest.mark.parametrize(
    "change,field",
    [
        ({"title": "   "}, "title"),
        ({"title": "x" * 201}, "title"),
        ({"description": "x" * 2001}, "description"),
        ({"university": " "}, "university"),
        ({"faculty": "x" * 161}, "faculty"),
        ({"program": "x"}, "program"),
        ({"degree": "invalid"}, "degree"),
        ({"academic_year": 1899}, "academic_year"),
        ({"academic_year": 2101}, "academic_year"),
        ({"academic_year": 2026.5}, "academic_year"),
        ({"academic_year": "2026"}, "academic_year"),
        ({"academic_year": True}, "academic_year"),
        ({"title": None}, "title"),
        ({"owner_id": "untrusted"}, "owner_id"),
    ],
)
def test_api_validation_on_create_and_update(client, change, field):
    created = client.post(URL, json=PAYLOAD).json()
    for method, path in ((client.post, URL), (client.put, f"{URL}/{created['id']}")):
        response = method(path, json=PAYLOAD | change)
        assert response.status_code == 422
        assert response.json()["errors"][field]
    assert client.get(f"{URL}/{created['id']}").json()["title"] == PAYLOAD["title"]


def test_whitespace_and_optional_fields(client):
    payload = {key: PAYLOAD[key] for key in ("title", "university", "program", "degree")}
    payload["title"] = "  Título ficticio  "
    response = client.post(URL, json=payload)
    assert response.status_code == 201
    assert response.json()["title"] == "Título ficticio"
    assert response.json()["description"] == ""
    assert response.json()["academic_year"] is None


def test_missing_fields_malformed_body_and_ids(client):
    assert client.post(URL, json={}).status_code == 422
    assert (
        client.post(
            URL, content="invalid", headers={"Content-Type": "application/json"}
        ).status_code
        == 422
    )
    assert client.get(f"{URL}/not-a-uuid").status_code == 422
    assert client.get(f"{URL}/{uuid4()}").json()["detail"] == "No se encontró el proyecto."


def test_list_returns_most_recently_updated_first(client):
    first = client.post(URL, json=PAYLOAD).json()
    second = client.post(URL, json=PAYLOAD).json()
    assert [item["id"] for item in client.get(URL).json()] == [second["id"], first["id"]]
    client.put(f"{URL}/{first['id']}", json=PAYLOAD)
    assert client.get(URL).json()[0]["id"] == first["id"]


def test_development_cors_supports_crud_only_for_configured_origin(client):
    for method in ("GET", "POST", "PUT", "DELETE"):
        response = client.options(
            URL,
            headers={
                "Origin": "http://localhost:5174",
                "Access-Control-Request-Method": method,
                "Access-Control-Request-Headers": "content-type",
            },
        )
        assert response.status_code == 200
        assert response.headers["access-control-allow-origin"] == "http://localhost:5174"
    denied = client.options(
        URL,
        headers={
            "Origin": "https://untrusted.example",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert denied.status_code == 400


def test_storage_failure_has_a_safe_error_message():
    repository = MemoryRepository()

    def fail():
        raise sqlite3.OperationalError("internal connection details")

    repository.list = fail
    with TestClient(create_app(repository=repository)) as client:
        response = client.get(URL)
    assert response.status_code == 503
    assert "internal" not in response.text


def test_model_does_not_require_methodology():
    draft = ProjectDraft(**PAYLOAD)
    assert "hypotheses" not in draft.model_dump()
    with pytest.raises(ValidationError):
        ProjectDraft(**(PAYLOAD | {"dataset": {}}))
