from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Event
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.modules.research.dev_app import create_app
from tests.research.test_diagnostics_v2 import diagnose, intention, source
from tests.research.test_diagnostics_v2 import setup as setup


def proposal(client, root, intent, diagnostics=None):
    r = client.post(
        root + "/analysis/plans",
        json={
            "intent_id": intent["id"],
            "intent_revision": intent["revision"],
            "dataset_id": intent["dataset_id"],
            "dataset_revision": 1,
            "diagnostic_ids": diagnostics or [],
        },
    )
    assert r.status_code == 201, r.text
    return r.json()


def approve(client, root, plan):
    authorization = client.post(
        root + f"/analysis/plans/{plan['id']}/authorize-data",
        json={"proposal_token": plan["proposal_token"], "confirm": True},
    )
    assert authorization.status_code == 200, authorization.text
    r = client.post(
        root + f"/analysis/plans/{plan['id']}/approve",
        json={"proposal_token": plan["proposal_token"], "confirm": True},
    )
    assert r.status_code == 200, r.text
    return r.json()


def execute(client, root, plan, request_id=None):
    return client.post(
        root + f"/analysis/plans/{plan['id']}/execute",
        json={"proposal_token": plan["proposal_token"], "request_id": request_id or str(uuid4())},
    )


def descriptive(client, root):
    ds, dictionary = source(client, root)
    intent = intention(
        client, root, ds, dictionary, kind="descriptive", estimand="summary", paired_columns=None
    )
    return intent


def test_descriptive_approval_idempotence_restart_and_history(setup):
    client, root, app, settings = setup
    intent = descriptive(client, root)
    plan = proposal(client, root, intent)
    assert plan["technique"] == "descriptive_summary", plan
    assert execute(client, root, plan).status_code == 409
    bad = client.post(
        root + f"/analysis/plans/{plan['id']}/approve",
        json={"proposal_token": "f" * 64, "confirm": True},
    )
    assert bad.status_code == 409
    approve(client, root, plan)
    request_id = str(uuid4())
    r = execute(client, root, plan, request_id)
    assert r.status_code == 200, r.text
    result = r.json()
    assert result["status"] == "completed", result
    assert result["case_counts"]["used"] == 3
    assert execute(client, root, plan, request_id).json()["id"] == result["id"]
    assert execute(client, root, plan).json()["id"] == result["id"]
    with TestClient(create_app(settings=settings)) as restarted:
        assert restarted.get(root + "/analysis/results").json()[0]["id"] == result["id"]
    client.patch(
        root + f"/intents/{intent['id']}",
        json={"expected_revision": 1, "changes": {"question": "Otra pregunta"}},
    )
    historical = client.get(root + f"/analysis/results/{result['id']}").json()
    assert historical["validity"] == "stale"
    assert historical["metrics"] == result["metrics"]
    assert execute(client, root, plan, request_id).json()["validity"] == "stale"


@pytest.mark.parametrize(
    "kind,estimand,observations,expected",
    [
        ("association", "linear_association", "independent", "pearson"),
        ("association", "monotonic_association", "independent", "spearman"),
        ("comparison", "mean_difference", "independent", "t_welch"),
        ("comparison", "distribution_difference", "independent", "mann_whitney"),
        ("comparison", "mean_difference", "paired", "t_paired"),
        ("comparison", "distribution_difference", "paired", "wilcoxon"),
    ],
)
def test_real_selector_and_execution(setup, kind, estimand, observations, expected):
    client, root, _, _ = setup
    ds, dictionary = source(
        client,
        root,
        "id,antes,despues,grupo\na,1,3,A\nb,2,6,A\nc,4,5,A\nd,8,9,B\ne,5,10,B\nf,7,13,B\ng,,14,B\n",
    )
    ids = {v["name"]["value"]: v["id"] for v in dictionary["variables"]}
    cols = {c["name"]: c["id"] for c in ds["columns"]}
    independent = kind == "comparison" and observations == "independent"
    conditions = {
        k: "yes"
        for k in [
            "linearity",
            "monotonicity",
            "difference_symmetry",
            "inference_reviewed",
            "influence_reviewed",
            "sampling_limit_accepted",
        ]
    }
    conditions["review_notes"] = (
        "Medidas revisadas; dispersión y diferencias pertinentes, muestra sintética con "
        "límites de generalización."
    )
    intent = intention(
        client,
        root,
        ds,
        dictionary,
        kind=kind,
        estimand=estimand,
        observations=observations,
        alternative="two-sided",
        conditions=conditions,
        variable_ids=[ids["antes"], ids["grupo"] if independent else ids["despues"]],
        group_column_id=cols["grupo"] if independent else None,
        paired_columns={"before_column_id": cols["antes"], "after_column_id": cols["despues"]}
        if observations == "paired"
        else None,
    )
    diagnostic = diagnose(client, root, intent).json()
    plan = proposal(client, root, intent, [diagnostic["id"]])
    assert plan["technique"] == expected, plan["pending_questions"]
    approve(client, root, plan)
    r = execute(client, root, plan)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "completed", r.json()
    assert r.json()["case_counts"]["used"] == 6
    assert any(m["key"] == "p_value" for m in r.json()["metrics"])


def test_clarification_persists_and_cannot_approve(setup):
    client, root, _, _ = setup
    ds, dictionary = source(client, root)
    i = intention(client, root, ds, dictionary, alternative="greater")
    plan = proposal(client, root, i)
    assert plan["status"] == "needs_clarification"
    assert any(q["field"] == "alternative" for q in plan["pending_questions"])
    assert (
        client.post(
            root + f"/analysis/plans/{plan['id']}/approve",
            json={"proposal_token": plan["proposal_token"], "confirm": True},
        ).status_code
        == 409
    )


def test_parallel_double_execution_only_one_result(setup):
    client, root, _, _ = setup
    plan = proposal(client, root, descriptive(client, root))
    approve(client, root, plan)
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(lambda _: execute(client, root, plan), range(2)))
    assert all(r.status_code in {200, 409} for r in responses)
    assert len(client.get(root + "/analysis/results").json()) == 1


def test_change_during_execution_keeps_audited_stale_output(setup, monkeypatch):
    client, root, app, _ = setup
    intent = descriptive(client, root)
    plan = proposal(client, root, intent)
    approve(client, root, plan)
    from app.orchestration import analysis_v2_service as module

    original = module.execute

    def changing(data):
        response = client.patch(
            root + f"/intents/{intent['id']}",
            json={"expected_revision": 1, "changes": {"question": "Cambio concurrente"}},
        )
        assert response.status_code == 200
        return original(data)

    monkeypatch.setattr(module, "execute", changing)
    r = execute(client, root, plan)
    assert r.status_code == 200, r.text
    assert r.json()["validity"] == "stale"
    assert r.json()["metrics"]


def test_two_intents_and_interrupted_lease(setup):
    client, root, app, _ = setup
    first = descriptive(client, root)
    second = descriptive(client, root)
    p1, p2 = proposal(client, root, first), proposal(client, root, second)
    approve(client, root, p1)
    client.patch(
        root + f"/intents/{second['id']}",
        json={"expected_revision": 1, "changes": {"question": "Cambio segundo"}},
    )
    assert client.get(root + f"/analysis/plans/{p1['id']}").json()["validity"] == "current"
    assert client.get(root + f"/analysis/plans/{p2['id']}").json()["validity"] == "stale"
    service = app.state.analysis_v2
    from app.orchestration.analysis_v2_service import now

    attempt = p1["id"] + ":" + str(uuid4())
    with service.store.transaction() as db:
        state = {
            "status": "running",
            "attempt_id": attempt,
            "lease_until": (now() - timedelta(seconds=1)).isoformat(),
        }
        service._put_state(db, first["project_id"], "execution", p1["id"], state)
        service._put_state(db, first["project_id"], "attempt", attempt, state)
    assert client.get(root + f"/analysis/plans/{p1['id']}").json()["execution_status"] == "failed"
    assert execute(client, root, p1).json()["status"] == "completed"


@pytest.mark.parametrize(
    "finish_order,change",
    [
        (order, change)
        for order in ("after_b", "during_b")
        for change in (None, "intent", "dictionary", "policy")
    ]
    + [("before_b", None)],
)
def test_expired_attempt_cannot_invalidate_retry(setup, monkeypatch, finish_order, change):
    from app.orchestration import analysis_v2_service as module

    client, root, app, _ = setup
    dataset, dictionary = source(client, root)
    intent = intention(
        client,
        root,
        dataset,
        dictionary,
        kind="descriptive",
        estimand="summary",
        paired_columns=None,
    )
    plan = proposal(client, root, intent)
    approve(client, root, plan)
    service, project = app.state.analysis_v2, intent["project_id"]
    plan_url = root + f"/analysis/plans/{plan['id']}"
    clock = datetime(2026, 11, 11, tzinfo=UTC)
    monkeypatch.setattr(module, "now", lambda: clock)
    original = module.execute
    started = [Event(), Event()]
    release = [Event(), Event()]
    calls = []

    def controlled(data):
        index = len(calls)
        calls.append(data)
        started[index].set()
        # Only a deadlock guard: the test advances through events, never sleeps.
        assert release[index].wait(10), "El test no liberó el cálculo"
        return original(data)

    monkeypatch.setattr(module, "execute", controlled)
    keys = [str(uuid4()), str(uuid4())]
    lease_reason = "El intento perdió su reserva; no acredita ejecución vigente."
    with ThreadPoolExecutor(max_workers=2) as pool:
        try:
            old = pool.submit(execute, client, root, plan, keys[0])
            assert started[0].wait(10)
            clock += timedelta(seconds=module.LEASE_SECONDS + 1)
            assert client.get(plan_url).json()["execution_status"] == "failed"
            recovered = service.store.get(project, "attempt", f"{plan['id']}:{keys[0]}")
            assert recovered["status"] == "failed"
            assert "interrupted" in recovered["error"]

            if finish_order == "before_b":
                release[0].set()
                assert old.result(timeout=10).json()["validity"] == "stale"

            retry = pool.submit(execute, client, root, plan, keys[1])
            assert started[1].wait(10)
            reserved = service.store.get(project, "execution", plan["id"])
            assert reserved["attempt_id"] == f"{plan['id']}:{keys[1]}"
            assert reserved["status"] == "running"
            assert execute(client, root, plan, keys[1]).status_code == 409
            assert execute(client, root, plan).status_code == 409
            if finish_order == "after_b":
                release[1].set()
                completed = retry.result(timeout=10)
                assert completed.status_code == 200, completed.text
                assert completed.json()["validity"] == "current"

            if change == "intent":
                changed = client.patch(
                    root + f"/intents/{intent['id']}",
                    json={"expected_revision": 1, "changes": {"question": "Otra pregunta"}},
                )
                assert changed.status_code == 200, changed.text
            elif change == "dictionary":
                changed = client.patch(
                    root + f"/data-tables/{dataset['id']}/dictionary",
                    json={
                        "expected_revision": dictionary["revision"],
                        "dataset_revision": 1,
                        "dataset_hash": dataset["hash"],
                        "changes": {intent["variable_ids"][0]: {"measurement_scale": "interval"}},
                    },
                )
                assert changed.status_code == 200, changed.text
            elif change == "policy":
                monkeypatch.setattr(module, "VERSIONS", {**module.VERSIONS, "engine": "changed"})

            state_before = service.store.get(project, "execution", plan["id"])
            release[0].set()
            old_response = old.result(timeout=10)
            assert old_response.status_code == 200, old_response.text
            historical = old_response.json()
            assert historical["validity"] == "stale"
            assert lease_reason in historical["stale_reasons"]
            assert historical["metrics"]
            # Includes B's lease, result_id and all other reservation fields.
            assert service.store.get(project, "execution", plan["id"]) == state_before
            if finish_order != "after_b":
                assert state_before == reserved
                release[1].set()
            completed = retry.result(timeout=10)
            assert completed.status_code == 200, completed.text
            result = completed.json()
        finally:
            for event in release:
                event.set()

    expected_validity = "stale" if change else "current"
    current_plan = client.get(plan_url).json()
    current_result = client.get(root + f"/analysis/results/{result['id']}").json()
    assert current_plan["execution_status"] == "completed"
    assert current_plan["validity"] == current_result["validity"] == expected_validity
    assert current_result["status"] == "completed"
    assert lease_reason not in current_plan["stale_reasons"]
    assert lease_reason not in current_result["stale_reasons"]
    invalidation = service.store.get(project, "invalidation", plan["id"])
    if change:
        assert invalidation["reasons"] == current_plan["stale_reasons"]
        assert invalidation["reasons"]
    else:
        assert invalidation is None
        assert current_plan["invalidated_at"] is None
        assert current_result["stale_reasons"] == []
    attempts = client.get(plan_url + "/attempts").json()
    assert {a["request_id"]: a["status"] for a in attempts} == {
        keys[0]: "failed",
        keys[1]: "completed",
    }
    for key, expected_id in (
        (keys[0], historical["id"]),
        (keys[1], result["id"]),
        (str(uuid4()), result["id"]),
    ):
        replay = execute(client, root, plan, key)
        assert replay.status_code == 200, replay.text
        assert replay.json()["id"] == expected_id
    assert len(calls) == 2
    assert len(client.get(plan_url + "/attempts").json()) == 2
    assert {r["id"] for r in client.get(root + "/analysis/results").json()} == {
        historical["id"],
        result["id"],
    }


def test_student_requires_explicit_request_and_justification(setup):
    client, root, _, _ = setup
    ds, dictionary = source(
        client,
        root,
        "id,antes,despues,grupo\na,1,2,A\nb,2,3,A\nc,3,5,A\nd,5,6,B\ne,8,8,B\nf,9,10,B\n",
    )
    ids = {v["name"]["value"]: v["id"] for v in dictionary["variables"]}
    cols = {c["name"]: c["id"] for c in ds["columns"]}
    conditions = {
        "inference_reviewed": "yes",
        "influence_reviewed": "yes",
        "sampling_limit_accepted": "yes",
        "review_notes": (
            "Revisión de escalas, grupos y dispersión; "
            "igualdad de varianzas justificada por el diseño de medición."
        ),
    }
    intent = intention(
        client,
        root,
        ds,
        dictionary,
        observations="independent",
        paired_columns=None,
        alternative="two-sided",
        variable_ids=[ids["antes"], ids["grupo"]],
        group_column_id=cols["grupo"],
        requested_technique="t_independent",
        conditions=conditions,
    )
    d = diagnose(client, root, intent).json()
    p = proposal(client, root, intent, [d["id"]])
    assert any(q["field"] == "conditions/pooled_variance_justified" for q in p["pending_questions"])
    revised = client.patch(
        root + f"/intents/{intent['id']}",
        json={
            "expected_revision": 1,
            "changes": {"conditions": {"pooled_variance_justified": "yes"}},
            "confirm": True,
        },
    ).json()
    d = diagnose(client, root, revised).json()
    p2 = proposal(client, root, revised, [d["id"]])
    assert p2["id"] != p["id"] and p2["technique"] == "t_independent"
    approve(client, root, p2)
    assert execute(client, root, p2).json()["status"] == "completed"


@pytest.mark.parametrize(
    "kind,estimand,extra",
    [
        ("comparison", "mean_difference", {"observations": "repeated"}),
        ("reliability", "internal_consistency", {}),
        ("association", "linear_association", {"requested_technique": "tukey"}),
    ],
)
def test_unsupported_design_instrument_and_technique_are_clarifications(
    setup, kind, estimand, extra
):
    client, root, _, _ = setup
    ds, dictionary = source(client, root)
    intent = intention(client, root, ds, dictionary, kind=kind, estimand=estimand, **extra)
    p = proposal(client, root, intent)
    assert p["status"] == "needs_clarification" and p["technique"] is None
    assert client.get(root + "/analysis/plans").json()[0]["pending_questions"]


def test_failed_attempt_replay_and_explicit_retry(setup, monkeypatch):
    client, root, app, _ = setup
    plan = proposal(client, root, descriptive(client, root))
    approve(client, root, plan)
    from app.orchestration import analysis_v2_service as module

    original = module.execute

    def fail_once(data):
        raise ArithmeticError("Precisión no disponible")

    monkeypatch.setattr(module, "execute", fail_once)
    key = str(uuid4())
    failed = execute(client, root, plan, key).json()
    assert (
        failed["status"] == "failed" and not failed["metrics"] and failed["interpretation"] is None
    )
    monkeypatch.setattr(module, "execute", original)
    assert execute(client, root, plan, key).json()["id"] == failed["id"]
    success = execute(client, root, plan).json()
    assert success["status"] == "completed" and success["id"] != failed["id"]
    assert len(client.get(root + f"/analysis/plans/{plan['id']}/attempts").json()) == 2


def test_derived_source_invalidation_and_project_isolation(setup):
    client, root, _, _ = setup
    ds, dictionary = source(client, root)
    recipe = {
        "kind": "prepare",
        "name": "Ventas derivadas sintéticas",
        "left_table_id": ds["id"],
        "operations": [
            {"type": "rename_column", "column_ids": [ds["columns"][0]["id"]], "new_name": "id"}
        ],
    }
    preview = client.post(root + "/table-preparations/preview", json=recipe).json()
    response = client.post(
        root + "/table-preparations/apply",
        json={"preview_id": preview["id"], "recipe_hash": preview["recipe_hash"], "confirm": True},
    )
    assert response.status_code == 201, response.text
    derived = response.json()["dataset_ref"]
    dictionary = client.get(root + f"/data-tables/{derived['id']}/dictionary").json()
    confirmed = client.patch(
        root + f"/data-tables/{derived['id']}/dictionary",
        json={
            "expected_revision": dictionary["revision"],
            "dataset_revision": 1,
            "dataset_hash": derived["hash"],
            "changes": {},
            "confirm_fields": [
                f"/variables/{v['id']}/measurement_scale" for v in dictionary["variables"]
            ],
        },
    )
    assert confirmed.status_code == 200, confirmed.text
    client.post(
        root + f"/data-tables/{derived['id']}/profile",
        json={"dataset_revision": 1, "dataset_hash": derived["hash"], "confirm": True},
    )
    intent = intention(
        client,
        root,
        derived,
        confirmed.json(),
        kind="descriptive",
        estimand="summary",
        paired_columns=None,
    )
    p = proposal(client, root, intent)
    approve(client, root, p)
    other = client.post("/api/research/projects", json={"title": "Otro dominio"}).json()
    assert (
        client.get(f"/api/v2/research/projects/{other['id']}/analysis/plans/{p['id']}").status_code
        == 404
    )
    result = execute(client, root, p).json()
    assert result["status"] == "completed"
    f = client.get(root + "/files").json()[0]
    sheet = f["sheets"][0]
    client.patch(
        root + f"/files/{f['id']}/sheets/{sheet['id']}",
        json={"expected_revision": f["revision"], "action": "exclude"},
    )
    assert client.get(root + f"/analysis/results/{result['id']}").json()["validity"] == "stale"
    assert (
        client.post(
            root + f"/analysis/plans/{p['id']}/approve",
            json={"proposal_token": p["proposal_token"], "confirm": True},
        ).status_code
        == 409
    )


def test_missing_evidence_is_persisted_and_new_proposal_resolves_it(setup):
    client, root, _, _ = setup
    r = client.post(
        root + "/intents",
        json={
            "expected_revision": 0,
            "changes": {"kind": "descriptive", "estimand": "summary"},
            "confirm": True,
        },
    )
    p = proposal(client, root, r.json())
    assert p["status"] == "needs_clarification" and p["snapshot_ref"] is None
    ds, dictionary = source(client, root)
    updated = client.patch(
        root + f"/intents/{r.json()['id']}",
        json={
            "expected_revision": 1,
            "changes": {"dataset_id": ds["id"], "variable_ids": [dictionary["variables"][1]["id"]]},
            "confirm": True,
        },
    ).json()
    p2 = proposal(client, root, updated)
    assert p2["status"] == "proposed" and p2["id"] != p["id"]


def test_wilcoxon_zero_counts_match_actual_test(setup):
    client, root, _, _ = setup
    ds, dictionary = source(
        client, root, "id,antes,despues,grupo\na,1,1,A\nb,2,3,A\nc,4,6,B\nd,8,,B\n"
    )
    intent = intention(
        client,
        root,
        ds,
        dictionary,
        estimand="distribution_difference",
        alternative="two-sided",
        conditions={
            "difference_symmetry": "yes",
            "influence_reviewed": "yes",
            "sampling_limit_accepted": "yes",
        },
    )
    d = diagnose(client, root, intent).json()
    p = proposal(client, root, intent, [d["id"]])
    assert p["technique"] == "wilcoxon"
    assert p["case_counts"] == {"total": 4, "used": 2, "excluded": 2, "pairs": 3, "groups": []}
    approve(client, root, p)
    r = execute(client, root, p).json()
    assert r["status"] == "completed", r
    assert next(m["value"] for m in r["metrics"] if m["key"] == "n") == r["case_counts"]["used"]


def test_all_rows_and_nonfinite_never_published_as_numbers(setup):
    client, root, _, _ = setup
    ds, dictionary = source(
        client,
        root,
        "id,antes,despues,grupo\n"
        + "".join(f"a{i},{i},{2 * i},A\n" for i in range(70))
        + "bad,1e999,1,A\n",
    )
    intent = intention(
        client, root, ds, dictionary, kind="descriptive", estimand="summary", paired_columns=None
    )
    p = proposal(client, root, intent)
    approve(client, root, p)
    r = execute(client, root, p).json()
    assert r["case_counts"]["used"] == 70 and r["case_counts"]["excluded"] == 1
    assert r["status"] == "completed"


def test_request_actor_confirmation_and_version_are_not_trusted(setup):
    client, root, _, _ = setup
    p = proposal(client, root, descriptive(client, root))
    for extra in (
        {"actor_ref": "browser"},
        {"schema_version": "1.0.0"},
        {"approval": {"actor_ref": "fake"}},
    ):
        response = client.post(
            root + f"/analysis/plans/{p['id']}/approve",
            json={"proposal_token": p["proposal_token"], "confirm": True, **extra},
        )
        assert response.status_code == 422
    response = client.post(
        root + f"/analysis/plans/{p['id']}/approve",
        json={"proposal_token": p["proposal_token"], "confirm": False},
    )
    assert response.status_code == 409
    response = client.post(
        root + f"/analysis/plans/{p['id']}/approve",
        json={"proposal_token": p["proposal_token"], "confirm": True},
    )
    assert response.status_code == 403


def test_ordered_categories_use_reviewed_order_not_numeric_codes(setup):
    client, root, _, _ = setup
    ds, dictionary = source(
        client,
        root,
        "id,antes,despues,grupo\na,bajo,alto,A\nb,medio,bajo,A\nc,alto,medio,B\nd,bajo,medio,B\ne,alto,alto,B\n",
        quantitative=False,
    )
    updates = {
        v["id"]: {"measurement_scale": "ordinal", "category_order": ["bajo", "medio", "alto"]}
        for v in dictionary["variables"]
        if v["name"]["value"] in {"antes", "despues"}
    }
    r = client.patch(
        root + f"/data-tables/{ds['id']}/dictionary",
        json={
            "expected_revision": 1,
            "dataset_revision": 1,
            "dataset_hash": ds["hash"],
            "changes": updates,
            "confirm_fields": [f"/variables/{id_}/measurement_scale" for id_ in updates],
        },
    )
    assert r.status_code == 200, r.text
    client.post(
        root + f"/data-tables/{ds['id']}/profile",
        json={"dataset_revision": 1, "dataset_hash": ds["hash"], "confirm": True},
    )
    i = intention(
        client,
        root,
        ds,
        r.json(),
        kind="association",
        estimand="monotonic_association",
        observations="independent",
        paired_columns=None,
        alternative="two-sided",
        conditions={
            "monotonicity": "yes",
            "influence_reviewed": "yes",
            "sampling_limit_accepted": "yes",
        },
    )
    d = diagnose(client, root, i).json()
    p = proposal(client, root, i, [d["id"]])
    assert p["technique"] == "spearman", p
    approve(client, root, p)
    result = execute(client, root, p).json()
    assert result["status"] == "completed", result
    from scipy.stats import spearmanr

    expected = spearmanr([1, 2, 3, 1, 3], [3, 1, 2, 2, 3]).statistic
    assert next(m["value"] for m in result["metrics"] if m["key"] == "rho") == pytest.approx(
        expected
    )


def test_source_change_between_approval_and_execution_blocks_calculation(setup, monkeypatch):
    client, root, app, _ = setup
    i = descriptive(client, root)
    p = proposal(client, root, i)
    approve(client, root, p)
    client.patch(
        root + f"/intents/{i['id']}",
        json={
            "expected_revision": 1,
            "changes": {"question": "Cambio antes de ejecutar"},
            "confirm": True,
        },
    )
    from app.orchestration import analysis_v2_service as module

    def forbidden(data):
        raise AssertionError("Must not calculate stale evidence")

    monkeypatch.setattr(module, "execute", forbidden)
    assert execute(client, root, p).status_code == 409
    assert client.get(root + "/analysis/results").json() == []


def test_identical_concurrent_request_has_one_attempt(setup):
    client, root, _, _ = setup
    p = proposal(client, root, descriptive(client, root))
    approve(client, root, p)
    key = str(uuid4())
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: execute(client, root, p, key), range(2)))
    assert all(r.status_code in {200, 409} for r in results)
    assert len(client.get(root + f"/analysis/plans/{p['id']}/attempts").json()) == 1
    assert execute(client, root, p, key).status_code == 200


def test_killed_worker_is_recovered_after_restart(tmp_path):
    import json
    import subprocess
    import sys
    import time
    from pathlib import Path

    from app.modules.research.dev_app import ResearchDevSettings

    script = tmp_path / "interrupted_worker.py"
    script.write_text(
        """
import sys,time,json
from pathlib import Path
from fastapi.testclient import TestClient
from app.modules.research.dev_app import ResearchDevSettings,create_app
from app.orchestration import analysis_v2_service as module
from tests.research.test_analysis_workflow_v2 import descriptive,proposal,approve,execute
storage=Path(sys.argv[1])
settings=ResearchDevSettings(_env_file=None,research_db_path=storage/'db.sqlite3',research_documents_path=storage/'documents',research_datasets_path=storage/'datasets')
module.LEASE_SECONDS=0.2
with TestClient(create_app(settings=settings)) as client:
    p=client.post('/api/research/projects',json={'title':'Interrupción sintética'}).json()
    root=f"/api/v2/research/projects/{p['id']}"
    plan=proposal(client,root,descriptive(client,root));approve(client,root,plan)
    def interrupted(data):
        (storage/'running.json').write_text(json.dumps({'root':root,'plan':plan}),encoding='utf-8')
        time.sleep(60)
        raise AssertionError('Worker should be stopped')
    module.execute=interrupted
    execute(client,root,plan)
""",
        encoding="utf-8",
    )
    import os

    env = {**os.environ, "PYTHONPATH": str(Path.cwd())}
    with (tmp_path / "worker.log").open("w", encoding="utf-8") as log:
        process = subprocess.Popen(
            [sys.executable, str(script), str(tmp_path)], env=env, stdout=log, stderr=log
        )
        try:
            deadline = time.monotonic() + 30
            marker = tmp_path / "running.json"
            while not marker.exists() and process.poll() is None and time.monotonic() < deadline:
                time.sleep(0.05)
            assert marker.exists(), (tmp_path / "worker.log").read_text(encoding="utf-8")
            state = json.loads(marker.read_text(encoding="utf-8"))
        finally:
            if process.poll() is None:
                process.terminate()
            process.wait(timeout=10)
    time.sleep(0.3)
    settings = ResearchDevSettings(
        _env_file=None,
        research_db_path=tmp_path / "db.sqlite3",
        research_documents_path=tmp_path / "documents",
        research_datasets_path=tmp_path / "datasets",
    )
    with TestClient(create_app(settings=settings)) as restarted:
        root, plan = state["root"], state["plan"]
        assert (
            restarted.get(root + f"/analysis/plans/{plan['id']}").json()["execution_status"]
            == "failed"
        )
        assert restarted.get(root + "/analysis/results").json() == []
        assert execute(restarted, root, plan).json()["status"] == "completed"
        assert len(restarted.get(root + f"/analysis/plans/{plan['id']}/attempts").json()) == 2


def test_unconfirmed_draft_with_data_is_a_durable_clarification(setup):
    client, root, _, _ = setup
    intent = descriptive(client, root)
    draft = client.patch(
        root + f"/intents/{intent['id']}",
        json={
            "expected_revision": 1,
            "changes": {"question": "Revisión sin confirmar"},
            "confirm": False,
        },
    ).json()
    plan = proposal(client, root, draft)
    assert plan["status"] == "needs_clarification" and plan["snapshot_ref"] is None
    assert any(q["field"] == "confirmation" for q in plan["pending_questions"])
    read = client.get(root + f"/analysis/plans/{plan['id']}").json()
    assert (
        read["validity"] == "current" and read["source_fingerprint"] == plan["source_fingerprint"]
    )
    revised = client.patch(
        root + f"/intents/{intent['id']}",
        json={
            "expected_revision": 2,
            "changes": {},
            "confirm": True,
        },
    ).json()
    new = proposal(client, root, revised)
    assert new["status"] == "proposed" and new["id"] != plan["id"]
    assert client.get(root + f"/analysis/plans/{plan['id']}").json()["validity"] == "stale"
