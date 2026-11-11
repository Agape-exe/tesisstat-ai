"""C6 regression: two distinct instruments, original -> score A -> score B."""

import json
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.modules.research.dev_app import create_app
from tests.research.test_instruments_v2 import confirm, execute, ok, preview, ready, structure
from tests.research.test_instruments_v2 import env as env


def chain(env, prepared_source=False):
    c, root, app, _ = env
    a_url, a, a_mapping, original, _ = ready(env)
    if prepared_source:
        p = ok(
            c.post(
                root + "/table-preparations/preview",
                json={
                    "kind": "prepare",
                    "name": "Fuente preparada",
                    "left_table_id": original["id"],
                    "operations": [
                        {
                            "type": "rename_column",
                            "column_ids": [original["columns"][1]["id"]],
                            "new_name": "respuesta_uno",
                        }
                    ],
                },
            ),
            201,
        )
        prepared = ok(
            c.post(
                root + "/table-preparations/apply",
                json={
                    "preview_id": p["id"],
                    "recipe_hash": p["recipe_hash"],
                    "confirm": True,
                },
            ),
            201,
        )["dataset_ref"]
        a_mapping = ok(
            c.put(
                a_url + "/mapping",
                json={
                    "expected_revision": a_mapping["revision"],
                    "instrument_revision": a["revision"],
                    "dataset_id": prepared["id"],
                    "dataset_revision": 1,
                    "confirm": True,
                    "item_columns": [
                        {"item_id": item["item_id"], "column_id": col["id"]}
                        for item, col in zip(a["items"], prepared["columns"][1:], strict=True)
                    ],
                },
            )
        )
    a_preview = ok(preview(c, a_url, a, a_mapping, column_name="score_a"), 201)
    a_score = ok(confirm(c, a_url, a_preview), 201)
    a_table = a_score["derived_dataset_ref"]
    content = structure()
    content["variables"][0]["name"] = "Instrumento B"
    content["scoring_rules"][0]["aggregation"] = "mean"
    b = ok(c.post(root + "/instruments", json={"expected_revision": 0, "structure": content}), 201)
    b_url = root + "/instruments/" + b["instrument_id"]
    b = ok(c.post(b_url + "/confirm", json={"expected_revision": 1, "confirm": True}))
    b_mapping = ok(
        c.put(
            b_url + "/mapping",
            json={
                "expected_revision": 0,
                "instrument_revision": b["revision"],
                "dataset_id": a_table["id"],
                "dataset_revision": 1,
                "item_columns": [
                    {"item_id": item["item_id"], "column_id": col["id"]}
                    for item, col in zip(b["items"], a_table["columns"][1:4], strict=True)
                ],
                "confirm": True,
            },
        )
    )
    b_preview = ok(preview(c, b_url, b, b_mapping, column_name="score_b"), 201)
    b_score = ok(confirm(c, b_url, b_preview), 201)
    # This order caused the original 201 -> 422 failure. The owner is B.
    assert [r["id"] for r in b_score["source_refs"] if r["kind"] == "instrument"] == [
        a["instrument_id"],
        b["instrument_id"],
    ]
    return {
        "A": a,
        "B": b,
        "A_url": a_url,
        "B_url": b_url,
        "A_score": a_score,
        "B_score": b_score,
        "A_preview": a_preview,
        "B_preview": b_preview,
        "A_mapping": a_mapping,
        "B_mapping": b_mapping,
        "original": original,
    }


def rewrite(repo, project, kind, id_, change):
    """Simulate pre-fix storage/corruption in this isolated test database only."""
    with repo.transaction() as db:
        value = repo.get(project, kind, id_, db)
        change(value)
        db.execute(
            "UPDATE data_workspace_revisions_v2 SET payload=? "
            "WHERE project_id=? AND kind=? AND resource_id=? AND revision=?",
            (json.dumps(value), project, kind, id_, value["revision"]),
        )


def b_analysis(env, values):
    c, root, _, _ = env
    table = values["B_score"]["derived_dataset_ref"]
    dictionary = ok(c.get(root + f"/data-tables/{table['id']}/dictionary"))
    variable = next(
        v
        for v in dictionary["variables"]
        if v["column_ids"] == [values["B_score"]["derived_column_id"]]
    )
    ok(
        c.patch(
            root + f"/data-tables/{table['id']}/dictionary",
            json={
                "expected_revision": dictionary["revision"],
                "dataset_revision": 1,
                "dataset_hash": table["hash"],
                "changes": {variable["id"]: {"measurement_scale": "interval"}},
                "confirm_fields": [f"/variables/{variable['id']}/measurement_scale"],
            },
        )
    )
    ok(
        c.post(
            root + f"/data-tables/{table['id']}/profile",
            json={
                "dataset_revision": 1,
                "dataset_hash": table["hash"],
                "confirm": True,
            },
        ),
        201,
    )
    intent = ok(
        c.post(
            root + "/intents",
            json={
                "expected_revision": 0,
                "confirm": True,
                "changes": {
                    "kind": "descriptive",
                    "estimand": "summary",
                    "dataset_id": table["id"],
                    "variable_ids": [variable["id"]],
                    "question": "Describir las puntuaciones B",
                },
            },
        ),
        201,
    )
    plan = ok(
        c.post(
            root + "/analysis/plans",
            json={
                "intent_id": intent["id"],
                "intent_revision": intent["revision"],
            },
        ),
        201,
    )
    assert plan["technique"] == "descriptive_summary", plan
    result = execute(c, root, plan)
    assert result["case_counts"]["used"] == 4
    assert next(m["value"] for m in result["metrics"] if m["key"].endswith(".mean")) == 2.75
    return result


@pytest.mark.parametrize("legacy", [False, True])
@pytest.mark.parametrize("prepared_source", [False, True])
def test_two_instruments_read_profile_analyze_retry_and_restart(env, legacy, prepared_source):
    c, root, app, settings = env
    values = chain(env, prepared_source)
    repo, project = app.state.data_workspace_service.repository, values["A"]["project_id"]
    if legacy:
        for key in ("A", "B"):
            rewrite(
                repo,
                project,
                "score",
                values[f"{key}_score"]["id"],
                lambda value: value.pop("instrument_id"),
            )
            # Expired previews still preserve the historical publication relationship.
            rewrite(
                repo,
                project,
                "score_preview",
                values[f"{key}_preview"]["id"],
                lambda value: value.update(
                    expires_at=(datetime.now(UTC) - timedelta(days=1)).isoformat()
                ),
            )
            values[f"{key}_score"].pop("instrument_id")
    else:
        assert values["B_score"]["instrument_id"] == values["B"]["instrument_id"]
    table = values["B_score"]["derived_dataset_ref"]
    rows = ok(c.get(root + f"/data-tables/{table['id']}/preview"))["rows"]
    assert rows == [
        ["a", "1", "5", "", "2.0", "1.0"],
        ["b", "2", "4", "3", "4.0", "2.0"],
        ["c", "3", "2", "1", "7.0", "3.5"],
        ["d", "4", "1", "2", "9.0", "4.5"],
        ["e", "", "3", "4", None, None],
    ]
    derived = ok(c.get(root + f"/derived-tables/{table['id']}"))
    assert derived["row_lineage"] == [
        {values["A_score"]["derived_dataset_ref"]["id"]: n} for n in range(1, 6)
    ]
    assert ok(c.get(values["A_url"] + "/scores")) == [values["A_score"]]
    assert ok(c.get(values["B_url"] + "/scores")) == [values["B_score"]]
    result = b_analysis(env, values)
    assert ok(c.get(root + f"/data-tables/{table['id']}/profile"))["state"] == "current"
    # Downstream C3 preparation also reads and verifies both instruments' ancestors.
    p = ok(
        c.post(
            root + "/table-preparations/preview",
            json={
                "kind": "prepare",
                "name": "Preparación posterior",
                "left_table_id": table["id"],
                "operations": [
                    {
                        "type": "rename_column",
                        "column_ids": [values["B_score"]["derived_column_id"]],
                        "new_name": "indice_b",
                    }
                ],
            },
        ),
        201,
    )
    prepared = ok(
        c.post(
            root + "/table-preparations/apply",
            json={
                "preview_id": p["id"],
                "recipe_hash": p["recipe_hash"],
                "confirm": True,
            },
        ),
        201,
    )
    assert ok(c.get(root + f"/data-tables/{prepared['id']}/preview"))["rows"] == rows
    key = str(uuid4())
    for request_id in (key, key, str(uuid4())):
        assert (
            ok(confirm(c, values["B_url"], values["B_preview"], request_id), 201)
            == values["B_score"]
        )
    assert len(repo.all(project, "score")) == 2
    assert len(repo.all(project, "score_derived")) == 2
    with TestClient(create_app(settings=settings)) as restarted:
        assert ok(restarted.get(root + f"/data-tables/{table['id']}/preview"))["rows"] == rows
        assert (
            ok(restarted.get(root + "/analysis/results/" + result["id"]))["validity"] == "current"
        )


@pytest.mark.parametrize(
    "instrument,change",
    [
        ("A", "rule"),
        ("B", "rule"),
        ("A", "mapping"),
        ("B", "mapping"),
        ("A", "dictionary"),
    ],
)
def test_each_instrument_and_original_source_invalidates_only_dependents(env, instrument, change):
    c, root, app, _ = env
    values = chain(env)
    result = b_analysis(env, values)
    ins, url = values[instrument], values[instrument + "_url"]
    if change == "rule":
        content = {field: ins[field] for field in structure()}
        content["scoring_rules"][0]["aggregation"] = "mean" if instrument == "A" else "sum"
        ok(c.patch(url, json={"expected_revision": ins["revision"], "structure": content}))
    elif change == "mapping":
        mapping = values[instrument + "_mapping"]
        links = [dict(m) for m in mapping["item_columns"]]
        links[0]["column_id"], links[1]["column_id"] = links[1]["column_id"], links[0]["column_id"]
        ok(
            c.put(
                url + "/mapping",
                json={
                    "expected_revision": mapping["revision"],
                    "instrument_revision": ins["revision"],
                    "dataset_id": mapping["dataset_ref"]["id"],
                    "dataset_revision": 1,
                    "item_columns": links,
                    "confirm": True,
                },
            )
        )
    else:
        original = values["original"]
        dictionary = ok(c.get(root + f"/data-tables/{original['id']}/dictionary"))
        ok(
            c.patch(
                root + f"/data-tables/{original['id']}/dictionary",
                json={
                    "expected_revision": dictionary["revision"],
                    "dataset_revision": 1,
                    "dataset_hash": original["hash"],
                    "changes": {
                        dictionary["variables"][1]["id"]: {"missing_markers": ["", "ausente"]}
                    },
                },
            )
        )
    a_id, b_id = [values[k + "_score"]["derived_dataset_ref"]["id"] for k in ("A", "B")]
    assert c.get(root + f"/data-tables/{b_id}/preview").status_code == 409
    assert ok(c.get(root + f"/data-tables/{b_id}/profile"))["state"] == "stale"
    historical = ok(c.get(root + "/analysis/results/" + result["id"]))
    assert historical["validity"] == "stale" and historical["metrics"] == result["metrics"]
    assert c.get(root + f"/data-tables/{a_id}/preview").status_code == (
        409 if instrument == "A" else 200
    )
    assert c.get(root + f"/data-tables/{values['original']['id']}/preview").status_code == 200
    for k in ("A", "B"):
        assert ok(c.get(values[k + "_url"] + "/scores")) == [values[k + "_score"]]
    assert ok(confirm(c, values["B_url"], values["B_preview"]), 201) == values["B_score"]
    assert len(app.state.data_workspace_service.repository.all(ins["project_id"], "score")) == 2


def test_publication_owner_does_not_depend_on_ancestor_order_and_rejects_cycles(env):
    c, root, app, _ = env
    values = chain(env)
    repo, project = app.state.data_workspace_service.repository, values["B"]["project_id"]
    score, table = values["B_score"], values["B_score"]["derived_dataset_ref"]
    for kind, id_ in (("score", score["id"]), ("score_derived", table["id"])):
        rewrite(repo, project, kind, id_, lambda value: value["source_refs"].reverse())
    assert c.get(root + f"/data-tables/{table['id']}/preview").status_code == 200
    for k in ("A", "B"):
        ins, mapping = values[k], values[k + "_mapping"]
        response = c.put(
            values[k + "_url"] + "/mapping",
            json={
                "expected_revision": mapping["revision"],
                "instrument_revision": ins["revision"],
                "dataset_id": table["id"],
                "dataset_revision": 1,
                "item_columns": mapping["item_columns"],
                "confirm": True,
            },
        )
        assert response.status_code == 422 and "ciclo" in response.json()["error"]["message"]
    assert c.get(root + f"/data-tables/{table['id']}/preview").status_code == 200


@pytest.mark.parametrize("corruption", ["owner", "preview", "receipt", "frozen_rule"])
def test_owner_must_match_verified_server_publication_links(env, corruption):
    c, root, app, _ = env
    values = chain(env)
    repo, project = app.state.data_workspace_service.repository, values["B"]["project_id"]
    score, table = values["B_score"], values["B_score"]["derived_dataset_ref"]
    if corruption == "owner":
        rewrite(
            repo,
            project,
            "score",
            score["id"],
            lambda value: value.update(instrument_id=values["A"]["instrument_id"]),
        )
    elif corruption == "preview":
        rewrite(repo, project, "score", score["id"], lambda value: value.pop("instrument_id"))
        rewrite(
            repo,
            project,
            "score_preview",
            values["B_preview"]["id"],
            lambda value: value.update(instrument_id=values["A"]["instrument_id"]),
        )
    elif corruption == "receipt":
        rewrite(
            repo,
            project,
            "scored_preview",
            values["B_preview"]["id"],
            lambda value: value.update(score_id=values["A_score"]["id"]),
        )
    else:
        replacement = str(uuid4())
        for kind, id_ in (("score", score["id"]), ("score_preview", values["B_preview"]["id"])):
            rewrite(repo, project, kind, id_, lambda value: value.update(rule_id=replacement))
    assert c.get(root + f"/data-tables/{table['id']}/preview").status_code == 503
