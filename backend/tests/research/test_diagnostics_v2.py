import json
import math
import sqlite3
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

from app.modules.research.dev_app import ResearchDevSettings, create_app
from app.shared.diagnostics_v2 import DiagnosticV2

CHECKS = [
    "complete_cases",
    "group_sizes",
    "paired_cases",
    "distribution",
    "normality",
    "homogeneity",
    "influence",
]


@pytest.fixture
def setup(tmp_path):
    settings = ResearchDevSettings(
        _env_file=None,
        research_db_path=tmp_path / "db.sqlite3",
        research_documents_path=tmp_path / "documents",
        research_datasets_path=tmp_path / "datasets",
    )
    app = create_app(settings=settings)
    with TestClient(app) as client:
        project = client.post("/api/research/projects", json={"title": "S04A sintético"}).json()
        root = f"/api/v2/research/projects/{project['id']}"
        yield client, root, app, settings


def source(
    client,
    root,
    text="id,antes,despues,grupo\na,1,0,A\nb,2,0,A\nc,4,0,B\nd,8,,B\n",
    quantitative=True,
):
    r = client.post(
        root + "/files", content=text.encode(), headers={"X-File-Name": "sintetico.csv"}
    )
    assert r.status_code == 201, r.text
    table = r.json()["sheets"][0]["table_id"]
    dataset = next(d for d in client.get(root + "/data-tables").json() if d["id"] == table)
    dictionary = client.get(root + f"/data-tables/{table}/dictionary").json()
    changes, confirmations = {}, []
    for v in dictionary["variables"]:
        scale = "ratio" if quantitative and v["name"]["value"] not in {"id", "grupo"} else "nominal"
        changes[v["id"]] = {"measurement_scale": scale}
        confirmations.append(f"/variables/{v['id']}/measurement_scale")
    r = client.patch(
        root + f"/data-tables/{table}/dictionary",
        json={
            "expected_revision": 0,
            "dataset_revision": 1,
            "dataset_hash": dataset["hash"],
            "changes": changes,
            "confirm_fields": confirmations,
        },
    )
    assert r.status_code == 200, r.text
    dictionary = r.json()
    r = client.post(
        root + f"/data-tables/{table}/profile",
        json={"dataset_revision": 1, "dataset_hash": dataset["hash"], "confirm": True},
    )
    assert r.status_code == 201, r.text
    return dataset, dictionary


def intention(client, root, dataset, dictionary, **overrides):
    variables = [
        v["id"] for v in dictionary["variables"] if v["name"]["value"] in {"antes", "despues"}
    ]
    columns = {c["name"]: c["id"] for c in dataset["columns"]}
    changes = {
        "question": "Cambio en mediciones",
        "kind": "comparison",
        "estimand": "mean_difference",
        "dataset_id": dataset["id"],
        "variable_ids": variables,
        "observations": "paired",
        "observational_unit": "Una persona",
        "identification": "Código estable y una fila por persona",
        "comparison_notes": "Misma medida en dos momentos; sin inferir causalidad",
        "identifier_column_id": columns.get("id"),
        "linkage": "same_row",
        "paired_columns": {
            "before_column_id": columns["antes"],
            "after_column_id": columns["despues"],
        },
    }
    changes.update(overrides)
    r = client.post(
        root + "/intents", json={"expected_revision": 0, "changes": changes, "confirm": True}
    )
    assert r.status_code == 201, r.text
    return r.json()


def diagnose(client, root, intent, checks=CHECKS):
    return client.post(
        root + "/diagnostics",
        json={
            "intent_id": intent["id"],
            "intent_revision": intent["revision"],
            "dataset_id": intent["dataset_id"],
            "dataset_revision": 1,
            "checks": checks,
            "confirm": True,
        },
    )


def test_paired_full_rows_differences_manual_shapiro_and_immutable_history(setup):
    client, root, app, settings = setup
    dataset, dictionary = source(client, root)
    intent = intention(client, root, dataset, dictionary)
    r = diagnose(client, root, intent)
    assert r.status_code == 201, r.text
    result = r.json()
    assert result["profile"]["complete_pair_count"] == 3
    assert result["profile"]["excluded_missing_count"] == 1
    normal = next(c for c in result["checks"] if c["name"] == "normality")
    # n=3: Shapiro W = ((4-1)/sqrt(2))^2 / (14/3) = 27/28.
    w = 27 / 28
    assert normal["statistic"] == pytest.approx(w, abs=1e-8)
    assert normal["p_value"] == pytest.approx(
        6 / math.pi * (math.asin(math.sqrt(w)) - math.pi / 3), abs=1e-8
    )
    assert "Diferencias" in normal["target"]
    assert (
        next(c for c in result["checks"] if c["name"] == "homogeneity")["status"] == "not_checked"
    )
    assert sorted(result["figures"][1]["y"]) == [1, 2, 4]
    DiagnosticV2.model_validate(result)
    frozen = app.state.diagnostic_service.store.get(
        intent["project_id"], "diagnostic", result["id"]
    )
    client.patch(
        root + f"/intents/{intent['id']}",
        json={"expected_revision": 1, "changes": {"question": "Otra pregunta"}},
    )
    stale = client.get(root + f"/diagnostics/{result['id']}").json()
    assert stale["state"] == "stale"
    assert stale["checks"] == result["checks"]
    assert (
        app.state.diagnostic_service.store.get(intent["project_id"], "diagnostic", result["id"])
        == frozen
    )
    with TestClient(create_app(settings=settings)) as restarted:
        assert restarted.get(root + f"/diagnostics/{result['id']}").json() == stale
    assert len(client.get(root + f"/intents/{intent['id']}/revisions").json()) == 2


def test_all_rows_not_preview_and_no_global_assumptions(setup):
    client, root, _, _ = setup
    dataset, dictionary = source(
        client,
        root,
        "id,antes,despues,grupo\n" + "".join(f"p{i},{i},{i + 1},A\n" for i in range(125)),
    )
    client.patch(
        root + "/context",
        json={
            "expected_revision": 0,
            "changes": {"observations": "paired"},
            "confirm_fields": ["/observations"],
        },
    )
    intent = intention(client, root, dataset, dictionary, observations="unknown", linkage="unknown")
    result = diagnose(client, root, intent).json()
    assert result["profile"]["complete_case_count"] == 125
    assert result["profile"]["complete_pair_count"] is None
    assert (
        next(c for c in result["checks"] if c["name"] == "paired_cases")["status"] == "not_checked"
    )
    assert intent["alternative"] == "unspecified"
    assert client.get(root.replace("/api/v2", "/api") + "/datasets").status_code == 200


@pytest.mark.parametrize("relationship", ["unavailable", "unknown"])
def test_unlinkable_pairs_never_compute_differences(setup, relationship):
    client, root, _, _ = setup
    dataset, dictionary = source(client, root)
    intent = intention(client, root, dataset, dictionary, linkage=relationship)
    result = diagnose(client, root, intent, ["paired_cases", "normality"]).json()
    assert result["status"] == "not_calculable"
    assert result["profile"]["complete_pair_count"] is None
    assert all(c["status"] == "not_checked" and c["details"] for c in result["checks"])
    assert not result["figures"]


def test_numeric_codes_remain_nominal(setup):
    client, root, _, _ = setup
    dataset, dictionary = source(client, root, quantitative=False)
    intent = intention(
        client,
        root,
        dataset,
        dictionary,
        kind="descriptive",
        estimand="summary",
        observations="unknown",
        paired_columns=None,
    )
    result = diagnose(client, root, intent).json()
    assert result["profile"]["complete_case_count"] == 3
    assert all(
        c["status"] == "not_checked"
        for c in result["checks"]
        if c["name"] in {"normality", "distribution", "influence"}
    )
    assert result["figures"] == []


def test_independent_groups_counts_and_hand_brown_forsythe(setup):
    client, root, _, _ = setup
    dataset, dictionary = source(
        client,
        root,
        "id,antes,despues,grupo\na,1,0,A\nb,2,0,A\nc,5,0,A\nd,2,0,B\ne,4,0,B\nf,8,0,B\ng,,0,B\n",
    )
    outcome, group = [
        v for v in dictionary["variables"] if v["name"]["value"] in {"antes", "grupo"}
    ]
    intent = intention(
        client,
        root,
        dataset,
        dictionary,
        variable_ids=[outcome["id"], group["id"]],
        observations="independent",
        paired_columns=None,
        group_column_id=group["column_ids"][0],
    )
    result = diagnose(client, root, intent).json()
    assert result["profile"]["group_counts"] == [
        {"label": "A", "count": 3},
        {"label": "B", "count": 3},
    ]
    check = next(c for c in result["checks"] if c["name"] == "homogeneity")
    assert check["statistic"] == pytest.approx(4 / 19, abs=1e-8)
    assert len([c for c in result["checks"] if c["name"] == "normality"]) == 2


def test_dictionary_stale_and_publication_race_rolls_back(setup, monkeypatch):
    client, root, app, _ = setup
    dataset, dictionary = source(client, root)
    intent = intention(client, root, dataset, dictionary)
    result = diagnose(client, root, intent).json()
    import app.orchestration.diagnostic_service as module

    original = module.evaluate

    def race(*args):
        value = original(*args)
        r = client.patch(
            root + f"/intents/{intent['id']}",
            json={"expected_revision": 1, "changes": {"identification": "Cambió la unidad"}},
        )
        assert r.status_code == 200
        return value

    monkeypatch.setattr(module, "evaluate", race)
    assert diagnose(client, root, intent).status_code == 409
    assert len(app.state.diagnostic_service.store.all(intent["project_id"], "diagnostic")) == 1
    assert client.get(root + f"/diagnostics/{result['id']}").json()["state"] == "stale"


def test_drafts_multiple_intents_cas_and_server_metadata(setup):
    client, root, _, _ = setup
    draft = client.post(
        root + "/intents", json={"expected_revision": 0, "changes": {"question": "Aún sin datos"}}
    ).json()
    assert draft["confirmation"] is None and draft["dataset_id"] is None

    def save(name):
        return client.patch(
            root + f"/intents/{draft['id']}",
            json={"expected_revision": 1, "changes": {"question": name}},
        ).status_code

    with ThreadPoolExecutor(2) as pool:
        assert sorted(pool.map(save, ["Edición A", "Edición B"])) == [200, 409]
    dataset, dictionary = source(client, root)
    intent = intention(client, root, dataset, dictionary)
    assert len(client.get(root + "/intents").json()) == 2
    for field in ["actor_ref", "confirmation", "source_refs", "project_id"]:
        assert (
            client.post(
                root + "/intents", json={"expected_revision": 0, "changes": {field: "forged"}}
            ).status_code
            == 422
        )
    other = client.post("/api/research/projects", json={"title": "Otro"}).json()["id"]
    foreign = f"/api/v2/research/projects/{other}"
    assert client.get(foreign + f"/intents/{intent['id']}").status_code == 404
    assert diagnose(client, foreign, intent).status_code == 404
    assert (
        client.post(
            foreign + "/intents",
            json={"expected_revision": 0, "changes": {"dataset_id": dataset["id"]}},
        ).status_code
        == 404
    )


@pytest.mark.parametrize(
    "values,expected",
    [([1, 1, 1], "not_checked"), ([1, 2], "not_checked"), (list(range(5001)), "not_checked")],
)
def test_shapiro_bounds_without_hidden_sampling(setup, values, expected):
    client, root, _, _ = setup
    dataset, dictionary = source(
        client,
        root,
        "id,antes,despues,grupo\n" + "".join(f"p{i},{v},0,A\n" for i, v in enumerate(values)),
    )
    intent = intention(client, root, dataset, dictionary)
    result = diagnose(client, root, intent, ["normality"]).json()
    assert result["checks"][0]["status"] == expected
    assert result["checks"][0]["case_count"] == len(values)


def test_diagnostic_storage_failure_does_not_publish(setup, monkeypatch):
    client, root, app, _ = setup
    dataset, dictionary = source(client, root)
    intent = intention(client, root, dataset, dictionary)
    original = app.state.diagnostic_service.store.put

    def fail_after_insert(*args):
        original(*args)
        raise sqlite3.OperationalError("synthetic failure")

    monkeypatch.setattr(app.state.diagnostic_service.store, "put", fail_after_insert)
    assert diagnose(client, root, intent).status_code == 503
    assert client.get(root + "/diagnostics").json() == []


def test_nonfinite_input_is_excluded_not_published(setup):
    client, root, _, _ = setup
    dataset, dictionary = source(
        client, root, "id,antes,despues,grupo\na,1,0,A\nb,NaN,0,A\nc,Infinity,0,B\nd,4,0,B\n"
    )
    intent = intention(client, root, dataset, dictionary)
    result = diagnose(client, root, intent).json()
    assert result["profile"]["excluded_invalid_count"] == 2
    json.dumps(result, allow_nan=False)


def test_dictionary_change_stales_history_and_blocks_new_evidence(setup):
    client, root, _, _ = setup
    dataset, dictionary = source(client, root)
    intent = intention(client, root, dataset, dictionary)
    evidence = diagnose(client, root, intent).json()
    v = dictionary["variables"][1]
    changed = client.patch(
        root + f"/data-tables/{dataset['id']}/dictionary",
        json={
            "expected_revision": 1,
            "dataset_revision": 1,
            "dataset_hash": dataset["hash"],
            "changes": {v["id"]: {"missing_markers": ["", "1"]}},
            "confirm_fields": [],
        },
    )
    assert changed.status_code == 200
    assert client.get(root + f"/diagnostics/{evidence['id']}").json()["state"] == "stale"
    assert diagnose(client, root, intent).status_code == 409
    client.post(
        root + f"/data-tables/{dataset['id']}/profile",
        json={
            "dataset_revision": 1,
            "dataset_hash": dataset["hash"],
            "confirm": True,
        },
    )
    updated = diagnose(client, root, intent).json()
    assert updated["profile"]["complete_case_count"] == 2
    assert updated["profile"]["excluded_missing_count"] == 2


def test_derived_table_checks_all_ancestors_without_activating_v1(setup):
    client, root, _, _ = setup
    dataset, dictionary = source(client, root)
    recipe = {
        "kind": "prepare",
        "name": "Copia derivada sintética",
        "left_table_id": dataset["id"],
        "operations": [
            {"type": "rename_column", "column_ids": [dataset["columns"][0]["id"]], "new_name": "id"}
        ],
    }
    preview = client.post(root + "/table-preparations/preview", json=recipe)
    assert preview.status_code == 201, preview.text
    p = preview.json()
    applied = client.post(
        root + "/table-preparations/apply",
        json={"preview_id": p["id"], "recipe_hash": p["recipe_hash"], "confirm": True},
    )
    assert applied.status_code == 201, applied.text
    derived = applied.json()["dataset_ref"]
    dd = client.get(root + f"/data-tables/{derived['id']}/dictionary").json()
    client.post(
        root + f"/data-tables/{derived['id']}/profile",
        json={"dataset_revision": 1, "dataset_hash": derived["hash"], "confirm": True},
    )
    intent = intention(client, root, derived, dd)
    evidence = diagnose(client, root, intent, ["complete_cases", "paired_cases"])
    assert evidence.status_code == 201, evidence.text
    assert evidence.json()["profile"]["complete_case_count"] == 3
    files = client.get(root + "/files").json()
    f, sheet = files[0], files[0]["sheets"][0]
    excluded = client.patch(
        root + f"/files/{f['id']}/sheets/{sheet['id']}",
        json={"expected_revision": f["revision"], "action": "exclude"},
    )
    assert excluded.status_code == 200, excluded.text
    assert diagnose(client, root, intent).status_code == 409
    historical = client.get(root + f"/diagnostics/{evidence.json()['id']}").json()
    assert historical["state"] == "stale"
    assert historical["checks"] == evidence.json()["checks"]


@pytest.mark.parametrize("identifier", ["a", "NA"])
def test_duplicate_or_missing_identifiers_do_not_certify_pairs(setup, identifier):
    client, root, _, _ = setup
    dataset, dictionary = source(
        client, root, f"id,antes,despues,grupo\na,1,0,A\n{identifier},2,0,A\nc,4,0,B\n"
    )
    intent = intention(client, root, dataset, dictionary)
    result = diagnose(client, root, intent, ["paired_cases", "normality"]).json()
    assert result["profile"]["complete_pair_count"] is None
    assert result["status"] == "not_calculable"
    assert "identificadores" in result["checks"][0]["details"]
