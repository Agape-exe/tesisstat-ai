import json
import sqlite3
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.modules.research.dev_app import ResearchDevSettings, create_app


@pytest.fixture
def env(tmp_path):
    settings = ResearchDevSettings(
        _env_file=None,
        research_db_path=tmp_path / "db.sqlite3",
        research_documents_path=tmp_path / "documents",
        research_datasets_path=tmp_path / "datasets",
    )
    app = create_app(settings=settings)
    with TestClient(app) as client:
        p = client.post("/api/research/projects", json={"title": "Experiencia de servicio"}).json()
        root = f"/api/v2/research/projects/{p['id']}"
        yield client, root, app, settings


def structure():
    v, d, indicator, *items = [str(uuid4()) for _ in range(6)]
    return {
        "variables": [{"variable_id": v, "name": "Experiencia de servicio"}],
        "dimensions": [{"dimension_id": d, "variable_id": v, "name": "Conjunto general declarado"}],
        "indicators": [
            {"indicator_id": indicator, "dimension_id": d, "name": "Respuestas declaradas"}
        ],
        "items": [
            {
                "item_id": id_,
                "variable_id": v,
                "dimension_id": d,
                "indicator_id": indicator,
                "text": f"Experiencia {n + 1}",
                "response_type": "numeric",
                "valid_min": 1,
                "valid_max": 5,
                "reverse_scored": n == 1,
                "reverse_rule": "min_plus_max_minus_value" if n == 1 else None,
            }
            for n, id_ in enumerate(items)
        ],
        "scoring_rules": [
            {
                "scoring_rule_id": str(uuid4()),
                "scope": "dimension",
                "dimension_id": d,
                "item_ids": items[:2],
                "aggregation": "sum",
            }
        ],
    }


def ok(r, code=200):
    assert r.status_code == code, r.text
    return r.json()


def ready(
    env, csv="id,i1,i2,i3\na,1,5,\nb,2,4,3\nc,3,2,1\nd,4,1,2\ne,,3,4\n", structure_payload=None
):
    client, root, app, settings = env
    source = ok(
        client.post(root + "/files", content=csv.encode(), headers={"X-File-Name": "servicio.csv"}),
        201,
    )
    ds = next(
        d
        for d in client.get(root + "/data-tables").json()
        if d["id"] == source["sheets"][0]["table_id"]
    )
    dic = client.get(root + f"/data-tables/{ds['id']}/dictionary").json()
    dic = ok(
        client.patch(
            root + f"/data-tables/{ds['id']}/dictionary",
            json={
                "expected_revision": 0,
                "dataset_revision": 1,
                "dataset_hash": ds["hash"],
                "changes": {
                    v["id"]: {"identifier_confirmed": v["name"]["value"] == "id"}
                    for v in dic["variables"]
                },
                "confirm_fields": [
                    f"/variables/{v['id']}/identifier_confirmed" for v in dic["variables"]
                ],
            },
        )
    )
    instrument = ok(
        client.post(
            root + "/instruments",
            json={"expected_revision": 0, "structure": structure_payload or structure()},
        ),
        201,
    )
    url = root + "/instruments/" + instrument["instrument_id"]
    assert (
        client.post(url + "/confirm", json={"expected_revision": 1, "confirm": True}).status_code
        == 409
    )
    ok(
        client.patch(
            root + "/context",
            json={
                "expected_revision": 0,
                "changes": {
                    "study_description": "Respuestas sobre experiencia de atención al cliente."
                },
                "confirm_fields": ["/study_description"],
            },
        )
    )
    instrument = ok(client.post(url + "/confirm", json={"expected_revision": 1, "confirm": True}))
    mapping_body = {
        "expected_revision": 0,
        "instrument_revision": instrument["revision"],
        "dataset_id": ds["id"],
        "dataset_revision": 1,
        "item_columns": [
            {"item_id": i["item_id"], "column_id": c["id"]}
            for i, c in zip(instrument["items"], ds["columns"][1:], strict=True)
        ],
        "confirm": True,
    }
    mapping = ok(client.put(url + "/mapping", json=mapping_body))
    return url, instrument, mapping, ds, dic


def preview(client, url, instrument, mapping, **kw):
    return client.post(
        url + "/score-previews",
        json={
            "expected_revision": instrument["revision"],
            "mapping_revision": mapping["revision"],
            "scoring_rule_id": instrument["scoring_rules"][0]["scoring_rule_id"],
            "confirm": True,
            **kw,
        },
    )


def confirm(client, url, p, request=None):
    return client.post(
        url + "/scores",
        json={
            "preview_id": p["id"],
            "fingerprint": p["fingerprint"],
            "confirm": True,
            "request_id": request or str(uuid4()),
        },
    )


def intent_ready(env, data):
    c, root, app, _ = env
    url, instrument, mapping, ds, dic = data
    ok(
        c.post(
            root + f"/data-tables/{ds['id']}/profile",
            json={"dataset_revision": 1, "dataset_hash": ds["hash"], "confirm": True},
        ),
        201,
    )
    i = ok(
        c.post(
            root + "/intents",
            json={
                "expected_revision": 0,
                "confirm": True,
                "changes": {
                    "kind": "reliability",
                    "estimand": "internal_consistency",
                    "dataset_id": ds["id"],
                    "variable_ids": [
                        v["id"] for v in dic["variables"] if v["name"]["value"] in {"i1", "i2"}
                    ],
                    "instrument_id": instrument["instrument_id"],
                    "instrument_revision": instrument["revision"],
                    "mapping_revision": mapping["revision"],
                    "scoring_rule_id": instrument["scoring_rules"][0]["scoring_rule_id"],
                    "question": "¿Qué consistencia interna tienen estos ítems de experiencia?",
                    "reliability_group": "Dos ítems de experiencia del cliente, "
                    "revisados como conjunto pertinente.",
                    "conditions": {"same_construct": "yes"},
                },
            },
        ),
        201,
    )
    diagnostic = ok(
        c.post(
            root + "/diagnostics",
            json={
                "intent_id": i["id"],
                "intent_revision": 1,
                "dataset_id": ds["id"],
                "dataset_revision": 1,
                "checks": ["complete_cases"],
                "confirm": True,
            },
        ),
        201,
    )
    plan = ok(
        c.post(
            root + "/analysis/plans",
            json={"intent_id": i["id"], "intent_revision": 1, "diagnostic_ids": [diagnostic["id"]]},
        ),
        201,
    )
    assert plan["technique"] == "cronbach_alpha", plan
    return plan, diagnostic


def execute(c, root, plan):
    url = root + "/analysis/plans/" + plan["id"]
    body = {"proposal_token": plan["proposal_token"], "confirm": True}
    ok(c.post(url + "/authorize-data", json=body))
    ok(c.post(url + "/approve", json=body))
    return ok(
        c.post(
            url + "/execute",
            json={"proposal_token": plan["proposal_token"], "request_id": str(uuid4())},
        )
    )


def test_manual_scoring_preserves_rows_no_alpha_idempotent_restart(env, monkeypatch):
    c, root, app, settings = env
    url, instrument, mapping, ds, _ = ready(env)

    def forbidden(*args, **kwargs):
        pytest.fail("El preview no debe calcular alfa")

    monkeypatch.setattr("app.modules.statistics.inferential.cronbach_alpha", forbidden)
    monkeypatch.setattr("app.modules.statistics.scoring.cronbach_alpha", forbidden)
    p = ok(preview(c, url, instrument, mapping), 201)
    assert p["bounded_preview"] == [2, 4, 7, 9, None]  # i3 absent does not affect this rule
    assert p["counts"] == {"total": 5, "valid": 4, "missing": 1, "unknown": 0, "out_of_range": 0}
    result = ok(confirm(c, url, p), 201)
    assert ok(confirm(c, url, p), 201) == result
    derived = result["derived_dataset_ref"]
    rows = ok(c.get(root + f"/data-tables/{derived['id']}/preview"))["rows"]
    assert [r[-1] for r in rows] == ["2.0", "4.0", "7.0", "9.0", None]
    assert [r[:-1] for r in rows] == ok(c.get(root + f"/data-tables/{ds['id']}/preview"))["rows"]
    assert derived["row_count"] == 5
    dictionary = ok(c.get(root + f"/data-tables/{derived['id']}/dictionary"))
    assert all(not v["measurement_scale"]["confirmation"] for v in dictionary["variables"])
    with TestClient(create_app(settings=settings)) as restarted:
        assert ok(restarted.get(url + "/scores")) == [result]
        assert ok(restarted.get(root + f"/data-tables/{derived['id']}/preview"))["rows"] == rows


def test_reliability_same_c5_path_known_alpha_and_stale(env):
    c, root, app, _ = env
    data = ready(env)
    plan, diagnostic = intent_ready(env, data)
    assert diagnostic["profile"]["complete_case_count"] == 4
    result = execute(c, root, plan)
    # recoded pairs (1,1),(2,2),(3,4),(4,5): alpha = 1 - Var(x-y)/Var(x+y)
    alpha = next(m["value"] for m in result["metrics"] if m["key"] == "alpha")
    assert alpha == pytest.approx(28 / 29)
    url, instrument, _, ds, _ = data
    content = {k: instrument[k] for k in structure()}
    content["items"][0]["reverse_scored"] = True
    content["items"][0]["reverse_rule"] = "min_plus_max_minus_value"
    changed = ok(
        c.patch(url, json={"expected_revision": instrument["revision"], "structure": content})
    )
    assert changed["status"] == "draft"
    assert ok(c.get(url + "/mapping"))["status"] == "stale"
    assert ok(c.get(root + "/analysis/results/" + result["id"]))["validity"] == "stale"
    assert len(ok(c.get(url + "/revisions"))) == 3


@pytest.mark.parametrize(
    "csv,expected,status",
    [
        ("id,i1,i2,i3\na,1,3,1\nb,2,4,2\nc,3,4,3\n", -6.0, "completed"),
        ("id,i1,i2,i3\na,1,5,1\n", None, "not_executed"),
        ("id,i1,i2,i3\na,,5,1\nb,2,,2\n", None, "not_executed"),
        ("id,i1,i2,i3\na,1,5,1\nb,1,5,2\n", None, "not_executed"),
    ],
)
def test_negative_insufficient_and_constant_alpha(env, csv, expected, status):
    c, root, _, _ = env
    plan, _ = intent_ready(env, ready(env, csv))
    result = execute(c, root, plan)
    assert result["status"] == status
    if expected is None:
        assert result["metrics"] == [] and result["interpretation"] is None
        assert result["warnings"]
    else:
        assert next(m["value"] for m in result["metrics"] if m["key"] == "alpha") == pytest.approx(
            expected
        )
        assert any("negativo" in w for w in result["warnings"])


def test_mapping_rejections_and_cas(env):
    c, root, _, _ = env
    url, ins, mapping, ds, _ = ready(env)
    body = {
        "expected_revision": mapping["revision"],
        "instrument_revision": ins["revision"],
        "dataset_id": ds["id"],
        "dataset_revision": 1,
        "item_columns": mapping["item_columns"],
        "confirm": True,
    }
    for links in (
        body["item_columns"][:1],
        [body["item_columns"][0]] * 3,
        [body["item_columns"][0] | {"column_id": ds["columns"][0]["id"]}]
        + body["item_columns"][1:],
    ):
        assert c.put(url + "/mapping", json=body | {"item_columns": links}).status_code == 422
    assert c.put(url + "/mapping", json=body | {"dataset_id": str(uuid4())}).status_code == 404
    assert c.put(url + "/mapping", json=body | {"expected_revision": 0}).status_code == 409
    assert c.patch(url, json={"expected_revision": 1, "structure": structure()}).status_code == 409


def test_expiration_changed_dependencies_and_atomic_failure(env, monkeypatch):
    c, root, app, settings = env
    url, instrument, mapping, ds, _ = ready(env)
    p = ok(preview(c, url, instrument, mapping), 201)
    repo = app.state.data_workspace_service.repository
    with repo.transaction() as db:
        value = p | {"expires_at": (datetime.now(UTC) - timedelta(seconds=1)).isoformat()}
        db.execute(
            "UPDATE data_workspace_revisions_v2 SET payload=? "
            "WHERE resource_id=? AND kind='score_preview'",
            (json.dumps(value), p["id"]),
        )
    assert confirm(c, url, p).status_code == 409
    p = ok(preview(c, url, instrument, mapping), 201)
    original = app.state.data_workspace_service.publish_score

    def failing(*args):
        original(*args)
        raise sqlite3.OperationalError("fallo simulado después de publicar")

    monkeypatch.setattr(app.state.data_workspace_service, "publish_score", failing)
    assert confirm(c, url, p).status_code == 503
    assert len(c.get(root + "/data-tables").json()) == 1
    assert c.get(url + "/scores").json() == []
    monkeypatch.setattr(app.state.data_workspace_service, "publish_score", original)
    assert confirm(c, url, p).status_code == 201


@pytest.mark.parametrize(
    "aggregation,expected",
    [("sum", [5, 6, None, None, None]), ("mean", [2.5, 3, None, None, None])],
)
def test_explicit_codes_limits_unknowns_and_rule_local_missing(env, aggregation, expected):
    c, root, app, _ = env
    data = ready(env, "id,i1,i2,i3\na,A,2,\nb,B,3,2\nc,Z,4,2\nd,A,9,3\ne,,1,1\n")
    url, ins, mapping, _, _ = data
    content = {k: ins[k] for k in structure()}
    content["items"][0].update(
        response_type="single_choice",
        response_options=[
            {"code": "A", "label": "Respuesta inicial", "numeric_value": 1},
            {"code": "B", "label": "Respuesta posterior", "numeric_value": 3},
        ],
    )
    content["scoring_rules"][0]["aggregation"] = aggregation
    ins = ok(c.patch(url, json={"expected_revision": 2, "structure": content}))
    ins = ok(c.post(url + "/confirm", json={"expected_revision": 3, "confirm": True}))
    mapping = ok(
        c.put(
            url + "/mapping",
            json={
                "expected_revision": 1,
                "instrument_revision": 4,
                "dataset_id": mapping["dataset_ref"]["id"],
                "dataset_revision": 1,
                "item_columns": mapping["item_columns"],
                "confirm": True,
            },
        )
    )
    p = ok(preview(c, url, ins, mapping), 201)
    assert p["bounded_preview"] == expected  # 2 -> 4, once, before aggregation
    assert p["counts"] == {"total": 5, "valid": 2, "missing": 1, "unknown": 1, "out_of_range": 1}
    assert len(p["exclusions"]) == 2
    assert preview(c, url, ins, mapping, column_name="i1").status_code == 422


def test_rule_changes_stale_preview_derivative_and_only_dependent_analyses(env):
    from tests.research.test_analysis_workflow_v2 import approve, descriptive, proposal
    from tests.research.test_analysis_workflow_v2 import execute as execute_independent

    c, root, app, _ = env
    independent = proposal(c, root, descriptive(c, root))
    approve(c, root, independent)
    unrelated_result = ok(execute_independent(c, root, independent))
    data = ready(env)
    url, ins, mapping, _, _ = data
    p = ok(preview(c, url, ins, mapping), 201)
    record = ok(confirm(c, url, p), 201)
    old = ok(preview(c, url, ins, mapping), 201)
    plan, _ = intent_ready(env, data)
    result = execute(c, root, plan)
    content = {k: ins[k] for k in structure()}
    content["scoring_rules"][0]["aggregation"] = "mean"
    ok(c.patch(url, json={"expected_revision": 2, "structure": content}))
    assert confirm(c, url, old).status_code == 409
    assert (
        c.get(root + f"/data-tables/{record['derived_dataset_ref']['id']}/preview").status_code
        == 409
    )
    assert ok(c.get(root + "/analysis/results/" + result["id"]))["validity"] == "stale"
    assert ok(c.get(root + "/analysis/results/" + unrelated_result["id"]))["validity"] == "current"
    assert ok(c.get(url + "/scores"))[0] == record


def test_concurrent_cas_and_confirmation_retries(env):
    from concurrent.futures import ThreadPoolExecutor

    c, root, app, _ = env
    url, ins, mapping, _, _ = ready(env)
    p = ok(preview(c, url, ins, mapping), 201)
    request_id = str(uuid4())
    with ThreadPoolExecutor(2) as pool:
        responses = list(pool.map(lambda _: confirm(c, url, p, request_id), range(2)))
    assert [r.status_code for r in responses] == [201, 201]
    assert responses[0].json() == responses[1].json()
    assert len(c.get(url + "/scores").json()) == 1
    body = {"expected_revision": 2, "structure": {k: ins[k] for k in structure()}}
    with ThreadPoolExecutor(2) as pool:
        responses = list(pool.map(lambda _: c.patch(url, json=body), range(2)))
    assert sorted(r.status_code for r in responses) == [200, 409]


def test_context_scope_foreign_table_and_reliability_requires_group(env):
    c, root, app, _ = env
    data = ready(env)
    url, ins, mapping, _, _ = data
    context = c.get(root + "/context").json()
    ok(
        c.patch(
            root + "/context",
            json={
                "expected_revision": context["revision"],
                "changes": {"sampling_notes": "Otro campo no consumido"},
            },
        )
    )
    assert c.get(url).json()["status"] == "reviewed"
    foreign = c.post("/api/research/projects", json={"title": "Cultivo de plantas"}).json()
    other = f"/api/v2/research/projects/{foreign['id']}"
    f = ok(
        c.post(
            other + "/files",
            content=b"altura,ancho\n1,2\n2,3\n",
            headers={"X-File-Name": "plantas.csv"},
        ),
        201,
    )
    assert (
        c.put(
            url + "/mapping",
            json={
                "expected_revision": 1,
                "instrument_revision": 2,
                "dataset_id": f["sheets"][0]["table_id"],
                "dataset_revision": 1,
                "item_columns": mapping["item_columns"],
                "confirm": True,
            },
        ).status_code
        == 404
    )
    plan, diagnostic = intent_ready(env, data)
    i = c.get(root + "/intents/" + plan["intent_id"]).json()
    changed = ok(
        c.patch(
            root + "/intents/" + i["id"],
            json={
                "expected_revision": i["revision"],
                "changes": {"reliability_group": "", "conditions": {"same_construct": "unknown"}},
                "confirm": True,
            },
        )
    )
    p = ok(
        c.post(
            root + "/analysis/plans",
            json={"intent_id": i["id"], "intent_revision": changed["revision"]},
        ),
        201,
    )
    assert p["status"] == "needs_clarification" and p["technique"] is None
    assert {q["field"] for q in p["pending_questions"]} >= {"reliability_group", "same_construct"}


def test_agricultural_ratings_explicit_mean(env):
    c, root, _, _ = env
    s = structure()
    s["variables"][0]["name"] = "Condiciones observadas del cultivo"
    s["dimensions"][0]["name"] = "Evaluación declarada de parcela"
    s["indicators"][0]["name"] = "Observaciones del cultivo"
    for item, text in zip(
        s["items"], ["Cobertura", "Estrés observado", "Aspecto general"], strict=True
    ):
        item["text"] = text
    s["scoring_rules"][0]["aggregation"] = "mean"
    url, instrument, mapping, _, _ = ready(env, structure_payload=s)
    p = ok(preview(c, url, instrument, mapping), 201)
    assert p["bounded_preview"] == [1, 2, 3.5, 4.5, None]
    assert ok(confirm(c, url, p), 201)["counts"]["valid"] == 4


def test_change_during_execution_is_historical_and_engine_changes_invalidate(env, monkeypatch):
    from app.orchestration import analysis_v2_service
    from app.shared.instruments_v2 import InstrumentEdit

    c, root, app, _ = env
    data = ready(env)
    url, ins, mapping, _, _ = data
    p = ok(preview(c, url, ins, mapping), 201)
    plan, _ = intent_ready(env, data)
    original = analysis_v2_service.execute

    def change_during_calculation(inputs):
        computed = original(inputs)
        body = InstrumentEdit(expected_revision=2, structure={k: ins[k] for k in structure()})
        app.state.instruments_v2.save(ins["project_id"], body, ins["instrument_id"])
        return computed

    monkeypatch.setattr(analysis_v2_service, "execute", change_during_calculation)
    result = execute(c, root, plan)
    assert result["status"] == "completed" and result["validity"] == "stale"
    assert result["metrics"]
    assert confirm(c, url, p).status_code == 409


def test_recoding_engine_dependency_and_confirmation_request_conflict(env, monkeypatch):
    c, root, app, _ = env
    url, ins, mapping, _, _ = ready(env)
    p = ok(preview(c, url, ins, mapping), 201)
    request_id = str(uuid4())
    result = ok(confirm(c, url, p, request_id), 201)
    newer = ok(preview(c, url, ins, mapping, column_name="otra"), 201)
    assert confirm(c, url, newer, request_id).status_code == 409
    monkeypatch.setattr("app.modules.statistics.instrument_v2.VERSION", "instrument-scoring-v3")
    assert confirm(c, url, newer).status_code == 409
    assert (
        c.get(root + f"/data-tables/{result['derived_dataset_ref']['id']}/preview").status_code
        == 409
    )
