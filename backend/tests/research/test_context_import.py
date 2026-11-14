import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.modules.research.context.import_models import ContextImport
from app.modules.research.context.import_parser import candidates, parse_response
from app.modules.research.context.repository import ContextError
from app.modules.research.dev_app import ResearchDevSettings, create_app


@pytest.fixture
def setup(tmp_path):
    settings = ResearchDevSettings(
        _env_file=None,
        research_db_path=tmp_path / "import.sqlite3",
        research_documents_path=tmp_path / "documents",
        research_datasets_path=tmp_path / "datasets",
    )
    with TestClient(create_app(settings=settings)) as client:
        project = client.post("/api/research/projects", json={"title": "Proyecto sintético"}).json()
        yield client, f"/api/v2/research/projects/{project['id']}/context", settings


def response(topic="ventas"):
    return {
        "format_version": "context-import-1.0",
        "title": f"Estudio de {topic}",
        "main_objective": f"Describir {topic}",
        "observational_unit": "Un registro",
        "design": "observational",
        "observations": "unknown",
        "specific_objectives": [{"ref": "o1", "text": f"Describir la distribución de {topic}"}],
        "hypotheses": [],
        "complementary_notes": [],
    }


def create(client, url, value=None, revision=0):
    res = client.post(
        url + "/suggestions",
        json={"response": json.dumps(value or response()), "expected_revision": revision},
    )
    assert res.status_code == 201, res.text
    return res.json()


def apply(client, url, suggestion, selected=None, confirm=False, proposal=None):
    return client.post(
        url + f"/suggestions/{suggestion['id']}/apply",
        json={
            "expected_revision": suggestion["base_revision"],
            "proposal": proposal or suggestion["proposal"],
            "selected_fields": selected
            if selected is not None
            else list(candidates(ContextImport.model_validate(suggestion["proposal"]))),
            "confirm": confirm,
        },
    )


@pytest.mark.parametrize("topic", ["ventas", "aprendizaje", "clima organizacional"])
@pytest.mark.parametrize("fenced", [False, True])
def test_topics_direct_markdown_partial_without_hypotheses(topic, fenced):
    text = json.dumps(response(topic))
    proposal, extra = parse_response(f"```json\n{text}\n```" if fenced else text)
    assert proposal.main_objective == f"Describir {topic}"
    assert proposal.hypotheses == [] and proposal.research_question is None and extra == []


@pytest.mark.parametrize(
    "text",
    [
        "{} {}",
        "Una introducción {}",
        "[]",
        "```json\n{}\n```\n```json\n{}\n```",
        '{"format_version":"context-import-1.0","design":"survey"}',
        '{"format_version":"context-import-1.0","design":42}',
        '{"format_version":"context-import-1.0","main_objective":5}',
        '{"format_version":"otro"}',
        '{"format_version":"context-import-1.0","actor_ref":"yo"}',
        '{"format_version":"context-import-1.0","x":NaN}',
        '{"format_version":"context-import-1.0","design":"unknown","design":"observational"}',
        '{"format_version":"context-import-1.0","specific_objectives":[{"ref":"o1","text":"x"},'
        '{"ref":"o1","text":"y"}]}',
        '{"format_version":"context-import-1.0","hypotheses":[{"ref":"h1","statement":"x",'
        '"objective_ref":"missing"}]}',
        json.dumps(
            {
                **response(),
                "specific_objectives": [{"ref": f"o{i}", "text": str(i)} for i in range(41)],
            }
        ),
        json.dumps({**response(), "main_objective": "x" * 2001}),
        "[" * 9 + "]" * 9,
        "x" * 120001,
        json.dumps({**response(), "extra": list(range(1500))}),
    ],
)
def test_invalid_is_actionable_without_echoing_paste(text):
    with pytest.raises(ContextError) as exc:
        parse_response(text)
    assert exc.value.status in (413, 422) and len(exc.value.message) < 1200


def test_extras_are_bounded_reviewable_notes():
    proposal, extra = parse_response(json.dumps({**response(), "periodo": {"desde": "2025"}}))
    assert extra == ["periodo"] and "2025" in proposal.complementary_notes[0]
    with pytest.raises(ContextError):
        parse_response(
            json.dumps(
                {
                    **response(),
                    "complementary_notes": [str(i) for i in range(20)],
                    "periodo": "2025",
                }
            )
        )


def test_preview_cancel_and_project_scope(setup):
    client, url, _ = setup
    original = client.get(url).json()
    suggestion = create(client, url)
    assert client.get(url).json() == original
    assert client.get(url + f"/suggestions/{suggestion['id']}").json() == suggestion
    other = client.post("/api/research/projects", json={"title": "Otro"}).json()["id"]
    assert (
        client.get(
            f"/api/v2/research/projects/{other}/context/suggestions/{suggestion['id']}"
        ).status_code
        == 404
    )
    assert (
        client.post(url + f"/suggestions/{suggestion['id']}/reject").json()["state"] == "rejected"
    )
    assert apply(client, url, suggestion).status_code == 409
    assert client.get(url).json() == original


def test_selection_preserves_existing_ids_and_nulls_links_and_provenance(setup):
    client, url, settings = setup
    previous = client.patch(
        url,
        json={
            "expected_revision": 0,
            "changes": {
                "main_objective": "Anterior",
                "research_question": "Pregunta previa",
                "specific_objectives": [{"text": "Objetivo anterior"}],
            },
            "confirm_fields": [],
        },
    ).json()
    value = response()
    value["hypotheses"] = [
        {
            "ref": "h1",
            "statement": "Existe asociación explícita",
            "objective_ref": "o1",
            "alternative": "two-sided",
        }
    ]
    suggestion = create(client, url, value, 1)
    invalid = apply(client, url, suggestion, ["hypotheses/h1"])
    assert invalid.status_code == 422
    assert client.get(url).json() == previous
    applied = apply(
        client, url, suggestion, ["specific_objectives/o1", "hypotheses/h1"], True
    ).json()
    result = applied["result"]
    assert result["main_objective"] == previous["main_objective"]
    assert result["research_question"] == previous["research_question"]
    assert result["specific_objectives"][0] == previous["specific_objectives"][0]
    objective = result["specific_objectives"][1]
    assert objective["id"] != "o1" and result["hypotheses"][0]["objective_id"] == objective["id"]
    assert objective["text"]["provenance"]["kind"] == "ai_suggestion"
    assert objective["text"]["confirmation"]["actor_ref"] == "local"
    assert apply(client, url, suggestion).json() == applied
    assert len(client.get(url + "/revisions").json()) == 2
    confirmed = client.patch(
        url,
        json={
            "expected_revision": 2,
            "changes": {},
            "confirm_fields": ["/specific_objectives/1/text"],
        },
    ).json()
    assert (
        confirmed["specific_objectives"][1]["text"]["provenance"] == objective["text"]["provenance"]
    )
    edited = client.patch(
        url,
        json={
            "expected_revision": 3,
            "changes": {
                "specific_objectives": [
                    {"id": o["id"], "text": "Corregido" if i == 1 else o["text"]["value"]}
                    for i, o in enumerate(result["specific_objectives"])
                ]
            },
            "confirm_fields": [],
        },
    ).json()
    assert edited["specific_objectives"][1]["text"]["provenance"] == objective["text"]["provenance"]
    with TestClient(create_app(settings=settings)) as restarted:
        assert restarted.get(url).json() == edited
        assert restarted.get(url + f"/suggestions/{suggestion['id']}").json() == applied
    project_id = url.split("/")[-2]
    project = client.get(f"/api/research/projects/{project_id}").json()
    assert project["title"] == "Proyecto sintético"


def test_stale_is_persisted_and_rereview_does_not_overwrite(setup):
    client, url, _ = setup
    suggestion = create(client, url)
    client.patch(url, json={"expected_revision": 0, "changes": {"main_objective": "Otra edición"}})
    assert apply(client, url, suggestion).status_code == 409
    assert client.get(url + f"/suggestions/{suggestion['id']}").json()["state"] == "stale"
    assert client.get(url).json()["main_objective"]["value"] == "Otra edición"
    newer = create(client, url, suggestion["proposal"], 1)
    assert apply(client, url, newer, ["observational_unit"]).status_code == 200
    assert client.get(url).json()["main_objective"]["value"] == "Otra edición"


def test_atomic_rollback_and_concurrent_retry(setup):
    client, url, settings = setup
    suggestion = create(client, url)
    with sqlite3.connect(settings.research_db_path) as conn:
        conn.execute(
            "CREATE TRIGGER fail_receipt BEFORE UPDATE ON context_suggestions_v2 "
            "BEGIN SELECT RAISE(ABORT,'synthetic failure'); END"
        )
    assert apply(client, url, suggestion).status_code == 503
    assert client.get(url).json()["revision"] == 0
    with sqlite3.connect(settings.research_db_path) as conn:
        conn.execute("DROP TRIGGER fail_receipt")
    barrier = Barrier(2)

    def attempt():
        barrier.wait()
        return apply(client, url, suggestion)

    with ThreadPoolExecutor(2) as pool:
        results = list(pool.map(lambda _: attempt(), range(2)))
    assert [r.status_code for r in results] == [200, 200]
    assert results[0].json() == results[1].json()
    assert len(client.get(url + "/revisions").json()) == 1


def test_duplicates_limits_forged_metadata_and_prompt(setup):
    client, url, _ = setup
    suggestion = create(client, url)
    assert apply(client, url, suggestion).status_code == 200
    again = create(client, url, revision=1)
    assert apply(client, url, again).status_code == 422
    assert client.get(url).json()["revision"] == 1
    assert "JSON Schema" in client.get(url + "/import-prompt").json()["prompt"]
    assert (
        client.post(
            url + "/suggestions", json={"expected_revision": 1, "response": "x" * 800001}
        ).status_code
        == 413
    )
    with pytest.raises(ValidationError):
        ContextImport.model_validate(
            {**response(), "hypotheses": [{"ref": "h1", "statement": "x", "id": str(uuid4())}]}
        )


@pytest.mark.parametrize(
    "name", ["ventas", "educacion", "encuesta-organizacional", "grupos-y-sesiones"]
)
def test_published_synthetic_examples_match_canonical_schema(name):
    from jsonschema import Draft202012Validator

    root = Path(__file__).resolve().parents[3]
    proposal, _ = parse_response(
        (root / "fixtures/context-import" / f"{name}.json").read_text("utf-8")
    )
    Draft202012Validator(ContextImport.model_json_schema()).validate(proposal.model_dump())


def test_combined_capacity_null_selection_and_manual_note_trace(setup):
    client, url, _ = setup
    client.patch(
        url,
        json={
            "expected_revision": 0,
            "changes": {"specific_objectives": [{"text": f"Guardado {i}"} for i in range(40)]},
        },
    )
    suggestion = create(client, url, revision=1)
    assert apply(client, url, suggestion, ["specific_objectives/o1"]).status_code == 422
    assert apply(client, url, suggestion, ["research_question"]).status_code == 422
    assert client.get(url).json()["revision"] == 1
    value = response()
    value["complementary_notes"] = ["Nota importada"]
    suggestion = create(client, url, value, 1)
    result = apply(client, url, suggestion, ["main_objective", "complementary_notes/0"]).json()[
        "result"
    ]
    assert result["main_objective"]["confirmation"] is None
    updated = client.patch(
        url,
        json={
            "expected_revision": 2,
            "changes": {
                "main_objective": "Objetivo corregido",
                "complementary_notes": ["Nota corregida"],
            },
        },
    ).json()
    assert updated["main_objective"]["provenance"] == result["main_objective"]["provenance"]
    assert (
        updated["complementary_notes"][0]["provenance"]
        == result["complementary_notes"][0]["provenance"]
    )


@pytest.mark.parametrize("legacy", ["paired", "independent", "repeated"])
def test_mixed_study_relationship_is_narrative_not_global(setup, legacy):
    client, url, _ = setup
    root = Path(__file__).resolve().parents[3]
    value = json.loads((root / "fixtures/context-import/grupos-y-sesiones.json").read_text("utf-8"))
    value["observations"] = legacy
    tables_url = url.removesuffix("context") + "data-tables"
    tables_before = client.get(tables_url).json()
    suggestion = create(client, url, value)
    proposal = suggestion["proposal"]
    assert proposal["observations"] == "unknown"
    assert legacy in proposal["complementary_notes"][-1]
    assert "anónimos" in proposal["study_description"]
    assert "identificador" in proposal["study_description"]
    assert "observations" not in candidates(ContextImport.model_validate(proposal))
    blocked = apply(client, url, suggestion, ["observations"])
    assert blocked.status_code == 422 and "cada análisis" in blocked.json()["error"]["message"]
    assert client.get(url).json()["revision"] == 0
    result = apply(client, url, suggestion, confirm=True).json()["result"]
    assert result["observations"]["value"] == "unknown"
    assert result["observations"]["confirmation"] is None
    assert [h["statement"]["value"] for h in result["hypotheses"]] == [
        h["statement"] for h in value["hypotheses"]
    ]
    assert [h["alternative"] for h in result["hypotheses"]] == ["unspecified", "unspecified"]
    assert client.get(tables_url).json() == tables_before
    assert apply(client, url, suggestion).json()["result"] == result


def test_legacy_pending_preview_does_not_rewrite_original_or_allow_global_apply(setup):
    client, url, settings = setup
    suggestion = create(client, url)
    with sqlite3.connect(settings.research_db_path) as connection:
        original = json.loads(
            connection.execute(
                "SELECT payload FROM context_suggestions_v2 WHERE id=?", (suggestion["id"],)
            ).fetchone()[0]
        )
        original["proposal"]["observations"] = "paired"
        connection.execute(
            "UPDATE context_suggestions_v2 SET payload=? WHERE id=?",
            (json.dumps(original), suggestion["id"]),
        )
    preview = client.get(url + f"/suggestions/{suggestion['id']}").json()
    assert preview["proposal"]["observations"] == "unknown"
    assert "paired" in preview["proposal"]["complementary_notes"][0]
    with sqlite3.connect(settings.research_db_path) as connection:
        stored = json.loads(
            connection.execute(
                "SELECT payload FROM context_suggestions_v2 WHERE id=?", (suggestion["id"],)
            ).fetchone()[0]
        )
    assert stored == original
    assert apply(client, url, original, ["observations"]).status_code == 422
    applied = apply(client, url, preview, ["main_objective", "complementary_notes/0"]).json()
    assert applied["proposal"]["observations"] == "paired"
    assert applied["result"]["observations"]["value"] == "unknown"
    assert applied["result"]["complementary_notes"][0]["provenance"]["kind"] == "ai_suggestion"


def test_preserve_legacy_context_and_directions_without_silent_migration(setup):
    client, url, settings = setup
    old = client.patch(
        url,
        json={
            "expected_revision": 0,
            "changes": {
                "observational_unit": "Texto general anterior",
                "observations": "paired",
                "hypotheses": [{"statement": "H1: efecto favorable", "alternative": "less"}],
            },
            "confirm_fields": ["/observational_unit", "/observations", "/hypotheses/0/statement"],
        },
    ).json()
    before = client.get(url + "/revisions").json()
    with sqlite3.connect(settings.research_db_path) as connection:
        rows_before = connection.execute(
            "SELECT payload FROM research_context_revisions_v2"
        ).fetchall()
    current = client.get(url).json()
    assert current["observations"] == old["observations"]
    assert not any(
        q["field"] in ("/observations", "/observational_unit") for q in current["pending_questions"]
    )
    assert "fila" not in " ".join(q["question"] for q in current["pending_questions"])
    with sqlite3.connect(settings.research_db_path) as connection:
        assert (
            connection.execute("SELECT payload FROM research_context_revisions_v2").fetchall()
            == rows_before
        )
    suggestion = create(client, url, {**response(), "observations": "independent"}, 1)
    result = apply(client, url, suggestion, ["main_objective"]).json()["result"]
    for name in ("observations", "observational_unit", "hypotheses"):
        assert result[name] == old[name]
    assert client.get(url + "/revisions").json()[1:] == before


def test_legacy_relation_limit_is_explicit_and_prompt_is_scoped(setup):
    client, url, _ = setup
    normalized, _ = parse_response(json.dumps({**response(), "observations": "paired"}))
    repeated, _ = parse_response(
        json.dumps(
            {
                **response(),
                "observations": "paired",
                "complementary_notes": [normalized.complementary_notes[0].upper()],
            }
        )
    )
    assert len(repeated.complementary_notes) == 1
    value = {
        **response(),
        "observations": "paired",
        "complementary_notes": [str(i) for i in range(20)],
    }
    result = client.post(
        url + "/suggestions", json={"expected_revision": 0, "response": json.dumps(value)}
    )
    assert result.status_code == 422 and "no se descartó" in result.json()["error"]["message"]
    assert client.get(url + "/suggestions").json() == []
    prompt = client.get(url + "/import-prompt").json()
    assert prompt["prompt_version"] == "context-prompt-1.1"
    for text in (
        "row_meaning",
        "observations=unknown",
        "H0",
        "H1",
        "favorable",
        "codificación",
        "unspecified",
    ):
        assert text in prompt["prompt"]
