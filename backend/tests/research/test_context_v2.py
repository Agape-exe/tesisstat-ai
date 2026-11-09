import sqlite3
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.modules.research.context.models import ContextPatch
from app.modules.research.context.repository import ContextError
from app.modules.research.context.sqlite_repository import SQLiteContextRepository
from app.modules.research.context.use_cases import ContextService
from app.modules.research.dev_app import ResearchDevSettings, create_app
from app.modules.research.projects.models import ProjectDraft
from app.modules.research.projects.sqlite_repository import SQLiteProjectRepository
from app.modules.research.projects.use_cases import ProjectService


@pytest.fixture
def setup(tmp_path):
    settings = ResearchDevSettings(
        _env_file=None,
        research_db_path=tmp_path / "context.sqlite3",
        research_documents_path=tmp_path / "documents",
        research_datasets_path=tmp_path / "datasets",
    )
    with TestClient(create_app(settings=settings)) as client:
        project = client.post("/api/research/projects", json={"title": "Estudio sintético"}).json()
        yield client, f"/api/v2/research/projects/{project['id']}/context", settings


def save(client, url, revision=0, changes=None, confirm=None):
    return client.patch(
        url,
        json={
            "expected_revision": revision,
            "changes": changes or {},
            "confirm_fields": confirm or [],
        },
    )


def test_virtual_get_does_not_write_and_missing_project_is_404(setup):
    client, url, settings = setup
    context = client.get(url).json()
    assert context["revision"] == 0 and context["state"] == "empty"
    assert context["updated_at"] is None
    assert context["design"]["value"] == "unknown"
    assert client.get(url + "/revisions").json() == []
    with sqlite3.connect(settings.research_db_path) as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM research_context_revisions_v2"
        ).fetchone() == (0,)
    for project_id in (str(uuid4()), "invalid"):
        missing = f"/api/v2/research/projects/{project_id}/context"
        for response in (
            client.get(missing),
            client.get(missing + "/revisions"),
            save(client, missing),
        ):
            assert response.status_code == 404
            assert response.json()["error"]["code"] == "resource_not_found"


def test_objective_only_persists_across_app_and_process_restart_with_history(setup):
    client, url, settings = setup
    first = save(client, url, changes={"main_objective": "  Describir ventas sintéticas  "}).json()
    assert first["main_objective"]["value"] == "Describir ventas sintéticas"
    assert first["main_objective"]["confirmation"] is None
    assert first["hypotheses"] == [] and first["state"] == "partial"
    assert first["revision"] == 1
    second = save(client, url, 1, {"main_objective": "Describir ventas por mes"}).json()
    assert second["revision"] == 2
    with TestClient(create_app(settings=settings)) as restarted:
        assert restarted.get(url).json() == second
        assert restarted.get(url + "/revisions").json() == [second, first]
    program = (
        "from pathlib import Path; from app.modules.research.context.sqlite_repository "
        "import SQLiteContextRepository; import sys; "
        "print(SQLiteContextRepository(Path(sys.argv[1])).get(sys.argv[2]).model_dump_json())"
    )
    import json

    result = subprocess.run(
        [
            sys.executable,
            "-X",
            "utf8",
            "-c",
            program,
            str(settings.research_db_path),
            first["project_id"],
        ],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert json.loads(result.stdout) == second


def test_confirm_is_separate_and_edit_preserves_unmodified_facts(setup):
    client, url, _ = setup
    saved = save(
        client, url, changes={"main_objective": "Describir", "observational_unit": "Una venta"}
    ).json()
    assert saved["main_objective"]["confirmation"] is None
    confirmed = save(client, url, 1, confirm=["/main_objective", "/observational_unit"]).json()
    assert confirmed["revision"] == 2
    for field in ("main_objective", "observational_unit"):
        confirmation = confirmed[field]["confirmation"]
        assert confirmation["actor_ref"] == "local" and confirmation["revision"] == 2
        assert confirmation["confirmed_at"].endswith("Z")
    edited = save(client, url, 2, {"main_objective": "Comparar"}).json()
    assert edited["main_objective"]["confirmation"] is None
    assert edited["observational_unit"] == confirmed["observational_unit"]
    again = save(client, url, 3, {"main_objective": "Describir meses"}, ["/main_objective"]).json()
    assert again["main_objective"]["confirmation"]["revision"] == 4
    cleared = save(client, url, 4, {"main_objective": None}).json()
    assert cleared["main_objective"]["value"] is None
    assert cleared["main_objective"]["confirmation"] is None
    assert cleared["observational_unit"] == confirmed["observational_unit"]
    assert len(client.get(url + "/revisions").json()) == 5


def test_ids_references_reorder_edit_and_remove_are_validated_atomically(setup):
    client, url, _ = setup
    first = save(
        client, url, changes={"specific_objectives": [{"text": "Primero"}, {"text": "Segundo"}]}
    ).json()
    a, b = first["specific_objectives"]
    assert str(UUID(a["id"])) == a["id"]
    second = save(
        client,
        url,
        1,
        {"hypotheses": [{"statement": "Existe asociación", "objective_id": a["id"]}]},
        ["/specific_objectives/0/text", "/specific_objectives/1/text", "/hypotheses/0/statement"],
    ).json()
    h = second["hypotheses"][0]
    assert (
        save(
            client, url, 2, {"specific_objectives": [{"id": b["id"], "text": "Segundo"}]}
        ).status_code
        == 422
    )
    assert client.get(url).json() == second
    third = save(
        client,
        url,
        2,
        {
            "specific_objectives": [
                {"id": b["id"], "text": "Segundo"},
                {"id": a["id"], "text": "Primero corregido"},
            ]
        },
    ).json()
    assert third["specific_objectives"][0] == second["specific_objectives"][1]
    assert third["specific_objectives"][1]["text"]["confirmation"] is None
    assert third["hypotheses"][0] == h
    edited_h = {
        "id": h["id"],
        "statement": h["statement"]["value"],
        "objective_id": b["id"],
        "alternative": "two-sided",
    }
    fourth = save(client, url, 3, {"hypotheses": [edited_h]}).json()
    assert fourth["hypotheses"][0]["id"] == h["id"]
    assert fourth["hypotheses"][0]["statement"]["confirmation"] is None
    fifth = save(client, url, 4, {"specific_objectives": None, "hypotheses": None}).json()
    assert fifth["hypotheses"] == [] and fifth["specific_objectives"] == []
    assert client.get(url + "/revisions").json()[-2] == second


@pytest.mark.parametrize(
    "changes,confirm",
    [
        ({"main_objective": "x" * 2001}, []),
        ({"main_objective": 12}, []),
        ({"design": "invented"}, []),
        ({"design": "unknown"}, ["/design"]),
        ({"main_objective": None}, ["/main_objective"]),
        ({"main_objective": "  "}, ["/main_objective"]),
        ({"specific_objectives": [{"text": "x"}] * 41}, []),
        ({"hypotheses": [{"statement": "x"}] * 41}, []),
        ({"complementary_notes": ["x"] * 21}, []),
        ({"complementary_notes": ["x" * 2001]}, []),
        ({"specific_objectives": [{"id": "fabricated", "text": "x"}]}, []),
        ({"hypotheses": [{"statement": "x", "objective_id": "missing"}]}, []),
        ({"main_objective": {"value": "x", "confirmation": {}}}, []),
        ({"owner_id": "forged"}, []),
        ({"title": "Duplicate"}, []),
        ({"main_objective": "x"}, ["main_objective"]),
        ({"main_objective": "x"}, ["/main_objective", "/main_objective"]),
    ],
)
def test_invalid_payload_is_422_and_does_not_write(setup, changes, confirm):
    client, url, _ = setup
    response = save(client, url, changes=changes, confirm=confirm)
    assert response.status_code == 422, response.text
    assert response.json()["error"]["code"] == "invalid_payload"
    assert client.get(url + "/revisions").json() == []


@pytest.mark.parametrize(
    "extra",
    [
        {"expected_revision": True},
        {"expected_revision": "0"},
        {"expected_revision": -1},
        {"actor_ref": "fake"},
        {"confirmation": {}},
        {"schema_version": "1.0.0"},
    ],
)
def test_cannot_fabricate_actor_confirmation_or_revision(setup, extra):
    client, url, _ = setup
    response = client.patch(
        url, json={"expected_revision": 0, "changes": {"main_objective": "x"}} | extra
    )
    assert response.status_code == 422


def test_unknown_null_limits_and_duplicate_ids(setup):
    client, url, _ = setup
    saved = save(
        client,
        url,
        changes={
            "design": "unknown",
            "observations": None,
            "main_objective": "  ",
            "specific_objectives": [{"text": "x" * 2000}],
        },
    ).json()
    assert saved["main_objective"]["value"] is None
    assert saved["observations"]["value"] is None
    assert saved["design"]["confirmation"] is None
    item = saved["specific_objectives"][0]
    response = save(client, url, 1, {"specific_objectives": [{"id": item["id"], "text": "x"}] * 2})
    assert response.status_code == 422
    assert client.get(url).json() == saved


def test_projects_and_histories_do_not_mix_and_stale_request_is_409(setup):
    client, url, _ = setup
    first = save(client, url, changes={"main_objective": "Uno"}).json()
    project = client.post("/api/research/projects", json={"title": "Segundo"}).json()
    other = f"/api/v2/research/projects/{project['id']}/context"
    assert client.get(other).json()["revision"] == 0
    assert client.get(other + "/revisions").json() == []
    assert save(client, other, changes={"main_objective": "Dos"}).status_code == 200
    stale = save(client, url, changes={"main_objective": "Obsoleto"})
    assert stale.status_code == 409 and stale.json()["error"]["current_revision"] == 1
    assert client.get(url).json() == first
    assert client.get(url + "/revisions").json() == [first]


def test_atomic_compare_and_append_allows_exactly_one_concurrent_writer(tmp_path):
    path = tmp_path / "atomic.sqlite3"
    projects = ProjectService(SQLiteProjectRepository(path))
    project = projects.create(ProjectDraft(title="Concurrencia sintética"))
    barrier = Barrier(2)

    def writer(value):
        service = ContextService(projects, SQLiteContextRepository(path), actor_ref="local")
        barrier.wait(timeout=10)
        try:
            return service.patch(
                str(project.id),
                ContextPatch(expected_revision=0, changes={"main_objective": value}),
            )
        except ContextError as exc:
            return exc

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(writer, ["A", "B"]))
    assert sum(isinstance(r, ContextError) and r.status == 409 for r in results) == 1
    repository = SQLiteContextRepository(path)
    history = repository.revisions(str(project.id))
    assert len(history) == 1 and history[0].main_objective.value in {"A", "B"}


def test_storage_failure_is_not_empty_context(setup, monkeypatch):
    client, url, _ = setup

    def fail(*args):
        raise sqlite3.OperationalError("synthetic unavailable")

    monkeypatch.setattr(SQLiteContextRepository, "get", fail)
    response = client.get(url)
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "storage_unavailable"


def test_patch_cors_is_allowed_and_local_guards_remain(setup):
    client, url, _ = setup
    response = client.options(
        url, headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "PATCH"}
    )
    assert response.status_code == 200
    assert client.get(url, headers={"Host": "external.invalid"}).status_code == 403


def test_omitting_hypothesis_metadata_preserves_links_and_confirmation(setup):
    client, url, _ = setup
    first = save(client, url, changes={"specific_objectives": [{"text": "Describir"}]}).json()
    objective_id = first["specific_objectives"][0]["id"]
    second = save(
        client,
        url,
        1,
        {
            "hypotheses": [
                {
                    "statement": "Mayor importe",
                    "objective_id": objective_id,
                    "alternative": "greater",
                }
            ]
        },
        ["/hypotheses/0/statement"],
    ).json()
    hypothesis = second["hypotheses"][0]
    third = save(
        client,
        url,
        2,
        {
            "hypotheses": [
                {
                    "id": hypothesis["id"],
                    "statement": "Mayor importe",
                }
            ]
        },
    ).json()
    assert third["hypotheses"][0] == hypothesis
    cleared = save(
        client,
        url,
        3,
        {
            "hypotheses": [
                {
                    "id": hypothesis["id"],
                    "statement": "Mayor importe",
                    "objective_id": None,
                }
            ]
        },
    ).json()
    assert cleared["hypotheses"][0]["objective_id"] is None
    assert cleared["hypotheses"][0]["alternative"] == "greater"
    assert cleared["hypotheses"][0]["statement"]["confirmation"] is None
