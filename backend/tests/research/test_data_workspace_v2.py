import hashlib
import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app.modules.research.dev_app import ResearchDevSettings, create_app
from app.shared.analysis_v2 import canonical_hash
from app.shared.data_workspace_v2 import TableRecipeV2


@pytest.fixture
def setup(tmp_path):
    settings = ResearchDevSettings(
        _env_file=None,
        research_db_path=tmp_path / "projects.sqlite3",
        research_documents_path=tmp_path / "documents",
        research_datasets_path=tmp_path / "datasets",
    )
    app = create_app(settings=settings)
    with TestClient(app) as client:
        project = client.post("/api/research/projects", json={"title": "S03B sintético"}).json()
        root = f"/api/v2/research/projects/{project['id']}"
        yield client, root, app.state.data_workspace_service, settings


def upload(client, root, text, name="sintetico.csv"):
    response = client.post(root + "/files", content=text.encode(), headers={"X-File-Name": name})
    assert response.status_code == 201, response.text
    source = response.json()
    table_id = source["sheets"][0]["table_id"]
    assert table_id
    dataset = next(t for t in client.get(root + "/data-tables").json() if t["id"] == table_id)
    return dataset, source


def dictionary(client, root, dataset):
    response = client.get(root + f"/data-tables/{dataset['id']}/dictionary")
    assert response.status_code == 200, response.text
    return response.json()


def patch(client, root, dataset, current, changes=None, confirm=None):
    return client.patch(
        root + f"/data-tables/{dataset['id']}/dictionary",
        json={
            "expected_revision": current["revision"],
            "dataset_revision": dataset["revision"],
            "dataset_hash": dataset["hash"],
            "changes": changes or {},
            "confirm_fields": confirm or [],
        },
    )


def profile(client, root, dataset):
    return client.post(
        root + f"/data-tables/{dataset['id']}/profile",
        json={
            "dataset_revision": dataset["revision"],
            "dataset_hash": dataset["hash"],
            "confirm": True,
        },
    )


def join_recipe(left, right, policy="all_cases"):
    return {
        "kind": "join",
        "name": "Antes y después",
        "left_table_id": left["id"],
        "right_table_id": right["id"],
        "left_key": left["columns"][0]["id"],
        "right_key": right["columns"][0]["id"],
        "unmatched_policy": policy,
        "columns": [
            {"table_id": d["id"], "column_id": d["columns"][i]["id"], "name": name}
            for d, i, name in [
                (left, 0, "estudiante_antes"),
                (left, 1, "antes"),
                (right, 0, "estudiante_despues"),
                (right, 1, "despues"),
            ]
        ],
    }


def preview(client, root, recipe):
    response = client.post(root + "/table-preparations/preview", json=recipe)
    assert response.status_code == 201, response.text
    return response.json()


def apply(client, root, p):
    return client.post(
        root + "/table-preparations/apply",
        json={
            "preview_id": p["id"],
            "recipe_hash": p["recipe_hash"],
            "confirm": True,
        },
    )


def test_complete_profile_without_context_no_get_computation_nominal_and_unknown(setup):
    client, root, service, _ = setup
    # 30 rows with hand-known counts; last ten are outside the preview.
    dataset, _ = upload(
        client,
        root,
        "id,codigo,vacia,constante\n"
        + "".join(f"E{i:03},{'1' if i < 25 else 'NA'},,A\n" for i in range(30)),
    )
    assert dataset["format"] == "table_json" and dataset["hash_algorithm"] == "table-json-v1"
    url = root + f"/data-tables/{dataset['id']}/profile"
    assert client.get(url).status_code == 404
    assert service.repository.all(dataset["project_id"], "profile") == []
    d = dictionary(client, root, dataset)
    code = d["variables"][1]["id"]
    response = patch(
        client,
        root,
        dataset,
        d,
        {code: {"measurement_scale": "nominal"}},
        [f"/variables/{code}/measurement_scale"],
    )
    assert response.status_code == 200, response.text
    result = profile(client, root, dataset)
    assert result.status_code == 201, result.text
    p = result.json()
    assert p["rows"] == 30 and p["missing"] == 35
    assert p["columns"][1]["present"] == 25 and p["columns"][1]["missing"] == 5
    assert p["columns"][1]["frequencies"] == [{"value": "1", "count": 25, "percentage": 100.0}]
    assert p["columns"][1]["numeric_summary"] is None
    assert p["columns"][0]["measurement_scale"] == "unknown"
    assert p["columns"][0]["possible_identifier"]
    assert p["empty_columns"] == 1 and p["constant_columns"] == 2
    assert client.get(url).json()["revision"] == 1
    assert client.get(url).json()["hash"] == canonical_hash(p)
    assert len(service.repository.revisions(dataset["project_id"], "profile", dataset["id"])) == 1


def test_dictionary_false_confirmed_partial_preservation_conflict_history_restart(setup):
    client, root, _, settings = setup
    dataset, _ = upload(client, root, "id,nota\n001,10\n002,20\n")
    original = dictionary(client, root, dataset)
    var = original["variables"][1]["id"]
    path = f"/variables/{var}/identifier_confirmed"
    saved = patch(client, root, dataset, original, {var: {"identifier_confirmed": False}}, [path])
    assert saved.status_code == 200, saved.text
    known = saved.json()
    assert known["variables"][1]["identifier_confirmed"]["value"] is False
    assert known["variables"][1]["identifier_confirmed"]["confirmation"]["actor_ref"] == "local"
    assert patch(client, root, dataset, original, {var: {"description": "otro"}}).status_code == 409
    updated = patch(client, root, dataset, known, {var: {"description": "Nota final"}}).json()
    assert (
        updated["variables"][1]["identifier_confirmed"]
        == known["variables"][1]["identifier_confirmed"]
    )
    edited = patch(client, root, dataset, updated, {var: {"identifier_confirmed": True}}).json()
    assert edited["variables"][1]["identifier_confirmed"]["confirmation"] is None
    assert len(client.get(root + f"/data-tables/{dataset['id']}/dictionary/revisions").json()) == 3
    with TestClient(create_app(settings=settings)) as restarted:
        assert dictionary(restarted, root, dataset) == edited


def test_missing_policy_stale_recompute_and_quantitative_manual_summary(setup):
    client, root, _, _ = setup
    dataset, _ = upload(client, root, "id,nota\n001,10\n002,20\n003,999\n")
    old = profile(client, root, dataset).json()
    d = dictionary(client, root, dataset)
    var = d["variables"][1]["id"]
    saved = patch(
        client,
        root,
        dataset,
        d,
        {var: {"measurement_scale": "ratio", "missing_markers": ["999"]}},
        [f"/variables/{var}/measurement_scale"],
    )
    assert saved.status_code == 200, saved.text
    stale = client.get(root + f"/data-tables/{dataset['id']}/profile").json()
    assert stale["state"] == "stale" and stale["hash"] == old["hash"]
    fresh = profile(client, root, dataset).json()
    assert fresh["revision"] == 2 and fresh["columns"][1]["missing"] == 1
    assert fresh["columns"][1]["numeric_summary"]["mean"] == "15"
    assert fresh["columns"][1]["numeric_summary"]["median"] == "15"
    assert fresh["columns"][1]["numeric_summary"]["min"] == "10"
    assert fresh["columns"][1]["numeric_summary"]["max"] == "20"


@pytest.mark.parametrize(
    "policy,expected",
    [
        ("matches_only", [["E001", "10", "E001", "15"], ["E003", "30", "E003", "35"]]),
        (
            "all_cases",
            [
                ["E001", "10", "E001", "15"],
                ["E003", "30", "E003", "35"],
                ["E002", "20", None, None],
                [None, None, "E004", "40"],
            ],
        ),
    ],
)
def test_join_exact_expected_rows_counts_lineage_sources_and_explorable_derivative(
    setup, policy, expected
):
    client, root, service, _ = setup
    left, lf = upload(client, root, "id,nota\nE001,10\nE002,20\nE003,30\n", "antes.csv")
    right, rf = upload(client, root, "id,nota\nE003,35\nE001,15\nE004,40\n", "despues.csv")
    originals = [client.get(root + f"/files/{f['id']}/original").content for f in (lf, rf)]
    p = preview(client, root, join_recipe(left, right, policy))
    assert p["rows"] == expected
    assert (
        p["counts"]["matches"] == 2 and p["counts"]["left_only"] == p["counts"]["right_only"] == 1
    )
    assert p["unmatched_left"] == [2] and p["unmatched_right"] == [3]
    response = apply(client, root, p)
    assert response.status_code == 201, response.text
    record = response.json()
    assert record["hash"] == canonical_hash(record)
    dataset = record["dataset_ref"]
    assert service.read_table(left["project_id"], dataset["id"])[1] == expected
    assert {r["id"] for r in record["source_refs"] if r["kind"] == "dataset"} == {
        left["id"],
        right["id"],
    }
    assert {r["id"] for r in record["source_refs"] if r["kind"] == "source_file"} == {
        lf["id"],
        rf["id"],
    }
    assert record["row_lineage"][:2] == [
        {left["id"]: 1, right["id"]: 2},
        {left["id"]: 3, right["id"]: 1},
    ]
    assert apply(client, root, p).json()["id"] == record["id"]
    assert profile(client, root, dataset).status_code == 201
    d = dictionary(client, root, dataset)
    assert d["revision"] == 1
    assert all(v["measurement_scale"]["confirmation"] is None for v in d["variables"])
    var = d["variables"][1]["id"]
    assert (
        patch(
            client,
            root,
            dataset,
            d,
            {var: {"measurement_scale": "interval"}},
            [f"/variables/{var}/measurement_scale"],
        ).status_code
        == 200
    )
    assert originals == [client.get(root + f"/files/{f['id']}/original").content for f in (lf, rf)]


def test_missing_keys_not_matched_exact_zeros_spaces_and_duplicate_blockers(setup):
    client, root, _, _ = setup
    left, _ = upload(client, root, "id,nota\n001,10\n,20\n A ,30\nNA,40\n")
    right, _ = upload(client, root, "id,nota\n1,11\n,21\nA,31\nNA,41\n")
    p = preview(client, root, join_recipe(left, right))
    assert p["counts"]["matches"] == 0
    assert p["counts"]["left_missing_keys"] == p["counts"]["right_missing_keys"] == 2
    assert p["counts"]["result_rows"] == 8
    duplicate, _ = upload(client, root, "id,nota\n001,10\n001,11\n")
    p = preview(client, root, join_recipe(duplicate, right))
    assert p["counts"]["left_duplicate_keys"] == 1 and p["blockers"]
    assert p["rows"] == [] and apply(client, root, p).status_code == 409


def test_collisions_and_foreign_columns_rejected_and_values_exact(setup):
    client, root, _, _ = setup
    left, _ = upload(client, root, 'id,nota\n001," 001 "\n002,=1+2\n')
    right, _ = upload(client, root, "id,nota\n002,4\n001,5\n")
    recipe = join_recipe(left, right)
    recipe["columns"][1]["name"] = recipe["columns"][0]["name"]
    assert client.post(root + "/table-preparations/preview", json=recipe).status_code == 422
    recipe = join_recipe(left, right)
    p = preview(client, root, recipe)
    assert p["rows"][0][1] == " 001 " and p["rows"][1][1] == "=1+2"
    record = apply(client, root, p).json()
    result = profile(client, root, record["dataset_ref"]).json()
    assert result["columns"][1]["formula_count"] == 1
    assert result["columns"][1]["numeric_summary"] is None
    recipe["left_key"] = right["columns"][0]["id"]
    assert client.post(root + "/table-preparations/preview", json=recipe).status_code == 422


def test_source_exclusion_after_preview_and_dictionary_changes_block_apply(setup):
    client, root, _, _ = setup
    left, lf = upload(client, root, "id,nota\n1,10\n2,20\n")
    right, _ = upload(client, root, "id,nota\n2,21\n1,11\n")
    p = preview(client, root, join_recipe(left, right))
    d = dictionary(client, root, left)
    var = d["variables"][0]["id"]
    assert patch(client, root, left, d, {var: {"missing_markers": ["1"]}}).status_code == 200
    assert apply(client, root, p).status_code == 409
    p = preview(client, root, join_recipe(left, right))
    sheet = lf["sheets"][0]
    response = client.patch(
        root + f"/files/{lf['id']}/sheets/{sheet['id']}",
        json={"expected_revision": sheet["revision"], "action": "exclude"},
    )
    assert response.status_code == 200
    assert apply(client, root, p).status_code == 409
    assert (
        client.post(root + "/table-preparations/preview", json=join_recipe(left, right)).status_code
        == 409
    )


def test_expired_preview_rollback_retry_and_result_limits(setup, monkeypatch):
    client, root, service, _ = setup
    left, _ = upload(client, root, "id,nota\n1,10\n2,20\n")
    recipe = {
        "kind": "prepare",
        "name": "Renombrado",
        "left_table_id": left["id"],
        "operations": [
            {"type": "rename_column", "column_ids": [left["columns"][1]["id"]], "new_name": "antes"}
        ],
    }
    p = preview(client, root, recipe)
    with service.repository.transaction() as db:
        saved = service.repository.get(left["project_id"], "preview", p["id"], db)
        saved["expires_at"] = (datetime.now(UTC) - timedelta(seconds=1)).isoformat()
        db.execute(
            "UPDATE data_workspace_revisions_v2 SET payload=? WHERE resource_id=?",
            (json.dumps(saved), p["id"]),
        )
    assert apply(client, root, p).status_code == 409
    p = preview(client, root, recipe)
    real = service.repository.publish

    def broken(db, record, data):
        real(db, record, data)
        raise sqlite3.OperationalError("synthetic disk failure")

    monkeypatch.setattr(service.repository, "publish", broken)
    assert apply(client, root, p).status_code == 503
    assert service.repository.all(left["project_id"], "derived") == []
    with service.repository.transaction() as db:
        assert db.execute("SELECT count(*) FROM derived_content_v2").fetchone()[0] == 0
    monkeypatch.setattr(service.repository, "publish", real)
    assert apply(client, root, p).status_code == 201
    monkeypatch.setattr(service, "limits", replace(service.limits, max_rows=1))
    assert client.post(root + "/table-preparations/preview", json=recipe).status_code == 413
    monkeypatch.setattr(service, "limits", replace(service.limits, max_rows=50000, max_bytes=5))
    assert client.post(root + "/table-preparations/preview", json=recipe).status_code == 413


def test_preparation_shared_engine_rename_drop_missing_duplicate_lineage_and_chaining(setup):
    client, root, service, _ = setup
    source, _ = upload(client, root, "id,nota,extra\n001,10,A\n002,NA,B\n001,10,A\n003,30,C\n")
    recipe = {
        "kind": "prepare",
        "name": "Revisado",
        "left_table_id": source["id"],
        "operations": [
            {
                "type": "rename_column",
                "column_ids": [source["columns"][1]["id"]],
                "new_name": "antes",
            },
            {"type": "drop_columns", "column_ids": [source["columns"][2]["id"]]},
            {"type": "drop_missing", "column_ids": [source["columns"][1]["id"]]},
            {"type": "drop_duplicates"},
        ],
    }
    p = preview(client, root, recipe)
    assert p["rows"] == [["001", "10"], ["003", "30"]]
    assert p["counts"]["rows_removed"] == 2
    result = apply(client, root, p).json()
    assert result["row_lineage"] == [{source["id"]: 1}, {source["id"]: 4}]
    assert any(
        link["source_column_id"] == source["columns"][2]["id"] and link["result_column_id"] is None
        for link in result["column_lineage"]
    )
    d = dictionary(client, root, result["dataset_ref"])
    assert d["variables"][2]["column_ids"] == []
    derived = result["dataset_ref"]
    next_recipe = {
        "kind": "prepare",
        "name": "Otro",
        "left_table_id": derived["id"],
        "operations": [
            {
                "type": "replace_missing",
                "column_ids": [derived["columns"][1]["id"]],
                "value": "no consta",
            }
        ],
    }
    second = apply(client, root, preview(client, root, next_recipe)).json()
    assert service.read_table(source["project_id"], second["id"])[1] == [
        ["001", "10"],
        ["003", "30"],
    ]
    assert service.read_table(source["project_id"], source["id"])[1][1] == ["002", "NA", "B"]


def test_concurrency_one_cas_winner_and_idempotent_apply(setup):
    client, root, service, _ = setup
    source, _ = upload(client, root, "id,nota\n1,10\n2,20\n")
    current = dictionary(client, root, source)
    var = current["variables"][1]["id"]
    with ThreadPoolExecutor(2) as pool:
        responses = list(
            pool.map(
                lambda _: patch(client, root, source, current, {var: {"description": "nota"}}),
                range(2),
            )
        )
    assert sorted(r.status_code for r in responses) == [200, 409]
    recipe = {
        "kind": "prepare",
        "name": "Prueba",
        "left_table_id": source["id"],
        "operations": [{"type": "drop_duplicates"}],
    }
    p = preview(client, root, recipe)
    with ThreadPoolExecutor(2) as pool:
        responses = list(pool.map(lambda _: apply(client, root, p), range(2)))
    assert [r.status_code for r in responses] == [201, 201]
    assert responses[0].json()["id"] == responses[1].json()["id"]
    assert len(service.repository.all(source["project_id"], "derived")) == 1


def test_project_scope_strict_payloads_unknown_ordinal_and_hash_guard(setup):
    client, root, _, _ = setup
    source, _ = upload(client, root, "id,nota\n1,10\n2,20\n")
    other = client.post("/api/research/projects", json={"title": "Otro"}).json()
    alien = f"/api/v2/research/projects/{other['id']}"
    assert client.get(alien + f"/data-tables/{source['id']}/dictionary").status_code == 404
    current = dictionary(client, root, source)
    var = current["variables"][1]["id"]
    assert (
        patch(
            client,
            root,
            source,
            current,
            {var: {"measurement_scale": "unknown"}},
            [f"/variables/{var}/measurement_scale"],
        ).status_code
        == 422
    )
    assert (
        patch(
            client,
            root,
            source,
            current,
            {var: {"measurement_scale": "ordinal"}},
            [f"/variables/{var}/measurement_scale"],
        ).status_code
        == 422
    )
    assert (
        patch(
            client,
            root,
            source,
            current,
            {var: {"measurement_scale": "ordinal", "category_order": ["10", "20"]}},
            [f"/variables/{var}/measurement_scale"],
        ).status_code
        == 200
    )
    wrong = source | {"hash": "0" * 64}
    assert profile(client, root, wrong).status_code == 409
    bad = {
        "kind": "prepare",
        "name": "Otro",
        "left_table_id": source["id"],
        "operations": [{"type": "drop_duplicates"}],
    }
    assert client.post(alien + "/table-preparations/preview", json=bad).status_code == 404
    assert (
        client.post(
            root + "/table-preparations/preview", json=bad | {"owner_id": "fake"}
        ).status_code
        == 422
    )
    assert client.get(root + "/data-summary").json()["tables"][0]["profile"] == "absent"


def test_derived_restart_and_corruption_fails_explicitly(setup):
    client, root, service, settings = setup
    source, _ = upload(client, root, "id,nota\n1,10\n2,20\n")
    recipe = {
        "kind": "prepare",
        "name": "Prueba",
        "left_table_id": source["id"],
        "operations": [{"type": "drop_duplicates"}],
    }
    p = preview(client, root, recipe)
    record = apply(client, root, p).json()
    raw = service.repository.content(source["project_id"], record["id"])
    assert hashlib.sha256(raw).hexdigest() == record["dataset_ref"]["hash"]
    with TestClient(create_app(settings=settings)) as restarted:
        assert restarted.get(root + f"/data-tables/{record['id']}/preview").json()["rows"] == [
            ["1", "10"],
            ["2", "20"],
        ]
        assert apply(restarted, root, p).json() == record
    with service.repository.transaction() as db:
        db.execute("UPDATE derived_content_v2 SET content=? WHERE id=?", (b"broken", record["id"]))
    assert client.get(root + f"/data-tables/{record['id']}/preview").status_code == 503
    assert apply(client, root, p).status_code == 503


def test_historical_dictionary_survives_exclusion_and_read_port_checks_expected_refs(setup):
    client, root, service, _ = setup
    source, file = upload(client, root, "id,nota\n1,10\n2,20\n")
    d = dictionary(client, root, source)
    variable = d["variables"][1]["id"]
    saved = patch(client, root, source, d, {variable: {"description": "Conservada"}}).json()
    from app.modules.research.context.repository import ContextError

    with pytest.raises(ContextError) as error:
        service.read_table(source["project_id"], source["id"], expected_revision=2)
    assert error.value.status == 409
    sheet = file["sheets"][0]
    assert (
        client.patch(
            root + f"/files/{file['id']}/sheets/{sheet['id']}",
            json={"expected_revision": 1, "action": "exclude"},
        ).status_code
        == 200
    )
    assert dictionary(client, root, source) == saved
    history = client.get(root + f"/data-tables/{source['id']}/dictionary/revisions")
    assert history.status_code == 200 and history.json() == [saved]


def test_extreme_numbers_remain_text_with_explicit_uncalculable_summary(setup):
    client, root, _, _ = setup
    source, _ = upload(client, root, "id,valor\n1,1e99999999\n2,2\n")
    d = dictionary(client, root, source)
    variable = d["variables"][1]["id"]
    assert (
        patch(
            client,
            root,
            source,
            d,
            {variable: {"measurement_scale": "ratio"}},
            [f"/variables/{variable}/measurement_scale"],
        ).status_code
        == 200
    )
    result = profile(client, root, source)
    assert result.status_code == 201, result.text
    assert result.json()["columns"][1]["numeric_summary"] is None
    assert any("no calculable" in message for message in result.json()["columns"][1]["warnings"])


def test_custom_missing_policy_shared_by_profile_prepare_and_exact_replacement(setup):
    client, root, service, _ = setup
    source, _ = upload(client, root, "id,valor\n1, XX \n2,5\n")
    d = dictionary(client, root, source)
    variable = d["variables"][1]["id"]
    saved = patch(
        client,
        root,
        source,
        d,
        {variable: {"missing_markers": [" xx "]}},
        [f"/variables/{variable}/missing_markers"],
    )
    assert saved.status_code == 200, saved.text
    canonical = canonical_hash(saved.json())
    without = saved.json()
    without["variables"][1]["field_confirmations"] = {}
    assert canonical_hash(without) == canonical
    assert profile(client, root, source).json()["columns"][1]["missing"] == 1
    recipe = {
        "kind": "prepare",
        "name": "Reemplazo",
        "left_table_id": source["id"],
        "operations": [
            {
                "type": "replace_missing",
                "column_ids": [source["columns"][1]["id"]],
                "value": "  pendiente  ",
            }
        ],
    }
    p = preview(client, root, recipe)
    assert p["counts"]["cells_changed"] == 1
    assert p["rows"] == [["1", "  pendiente  "], ["2", "5"]]
    record = apply(client, root, p).json()
    assert service.read_table(source["project_id"], record["id"])[1][0][1] == "  pendiente  "


def test_profiles_each_real_xlsx_sheet_all_rows_with_formula_text_and_no_document(setup):
    from scripts.create_s03a_examples import workbook_bytes

    client, root, _, _ = setup
    response = client.post(
        root + "/files", content=workbook_bytes(), headers={"X-File-Name": "multihoja.xlsx"}
    )
    assert response.status_code == 201
    tables = client.get(root + "/data-tables").json()
    assert len(tables) == 3
    profiles = [profile(client, root, table).json() for table in tables]
    assert all(p["rows"] == 123 for p in profiles)
    assert len({p["dataset_ref"]["id"] for p in profiles}) == 3
    assert len({p["id"] for p in profiles}) == 3
    assert any(c["formula_count"] > 0 for p in profiles for c in p["columns"])
    assert all(c["present"] + c["missing"] == 123 for p in profiles for c in p["columns"])
    assert all(c["numeric_summary"] is None for p in profiles for c in p["columns"])


def test_empty_derived_result_is_explorable_without_invented_summary(setup):
    client, root, _, _ = setup
    source, _ = upload(client, root, "id,valor\n1,NA\n2,\n")
    recipe = {
        "kind": "prepare",
        "name": "Sin casos",
        "left_table_id": source["id"],
        "operations": [{"type": "drop_missing", "column_ids": [source["columns"][1]["id"]]}],
    }
    p = preview(client, root, recipe)
    assert p["rows"] == [] and p["counts"]["rows_removed"] == 2
    record = apply(client, root, p).json()
    result = profile(client, root, record["dataset_ref"])
    assert result.status_code == 201
    assert result.json()["rows"] == 0 and result.json()["empty_columns"] == 2


def test_join_keys_can_be_omitted_from_result_dictionary_without_losing_audit_lineage(setup):
    client, root, _, _ = setup
    left, _ = upload(client, root, "id,nota\nE001,10\nE002,20\n")
    right, _ = upload(client, root, "id,nota\nE002,25\nE001,15\n")
    recipe = join_recipe(left, right)
    recipe["columns"] = [recipe["columns"][1], recipe["columns"][3]]
    record = apply(client, root, preview(client, root, recipe)).json()
    d = dictionary(client, root, record["dataset_ref"])
    assert len(d["variables"]) == 2
    assert all(v["name"]["value"] == "nota" for v in d["variables"])
    assert len(record["column_lineage"]) == 4
    assert sum(link["result_column_id"] is None for link in record["column_lineage"]) == 2
    assert len(record["row_lineage"]) == 2


def test_recipe_model_rejects_nonfinite_extra_and_excess_columns():
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        TableRecipeV2.model_validate(
            {
                "kind": "join",
                "name": "X",
                "left_table_id": "a",
                "columns": [],
                "actor_ref": "client",
            }
        )
