import json
from io import BytesIO
from uuid import uuid4

import pytest
from docx import Document
from fastapi.testclient import TestClient
from pypdf import PdfReader

from app.modules.research.dev_app import create_app
from app.shared.ai_errors import AIError
from tests.research.test_analysis_workflow_v2 import approve, descriptive, execute, proposal
from tests.research.test_diagnostics_v2 import setup as setup
from tests.research.test_diagnostics_v2 import source


class Provider:
    configured = True

    def __init__(self, response=None):
        self.calls = []
        self.response = response or {
            "response_version": "tutor-2.1",
            "concepts": ["Revisa las métricas guardadas y sus limitaciones."],
        }
        self.error = None
        self.hook = None

    def chat(self, messages, *, max_tokens):
        self.calls.append(messages)
        if self.hook:
            self.hook()
        if self.error:
            raise AIError(self.error)
        return json.dumps(self.response, ensure_ascii=False)


def tutor(setup, response=None):
    client, root, app, settings = setup
    provider = Provider(response)
    app.state.tutor.conversations.provider = provider
    old = root.replace("/api/v2/", "/api/") + "/conversations"
    cid = client.post(old, json={}).json()["id"]
    consent = client.put(
        root + "/conversations/consent",
        json={"expected_revision": 0, "granted": True, "consent_scope": "tutor_context_v4"},
    )
    assert consent.status_code == 200, consent.text
    return client, root, provider, cid


def send(client, root, cid, **changes):
    body = {
        "content": "Explica mis resultados",
        "request_id": str(uuid4()),
        "stage": "home",
        "external_ai_consent": True,
        "consent_scope": "tutor_context_v4",
        "consent_revision": 1,
    }
    body.update(changes)
    return client.post(root + f"/conversations/{cid}/messages", json=body)


def test_empty_project_help_no_document_no_hypothesis_no_provider(setup):
    client, root, app, _ = setup
    status = client.get(root + "/conversations/status?stage=home")
    assert status.status_code == 200, status.text
    assert "opcionales" in status.json()["static_help"]
    assert not status.json()["context"]["current_result_ref"]
    assert status.json()["consent"]["granted"] is False
    old = root.replace("/api/v2/", "/api/") + "/conversations"
    cid = client.post(old, json={}).json()["id"]
    assert send(client, root, cid).status_code == 403
    assert send(client, root, cid, consent_scope="research_context_v2").status_code == 422
    client.put(
        root + "/conversations/consent",
        json={"expected_revision": 0, "granted": True, "consent_scope": "tutor_context_v4"},
    )
    app.state.tutor.conversations.provider = Provider()
    app.state.tutor.conversations.provider.configured = False
    assert send(client, root, cid).status_code == 503
    assert client.get(old + "/" + cid).status_code == 200


def test_stage_fingerprint_and_both_messages_persist_with_exact_retry(setup):
    client, root, provider, cid = tutor(setup)
    request_id = str(uuid4())
    first = send(client, root, cid, request_id=request_id)
    assert first.status_code == 200, first.text
    messages = first.json()["messages"]
    assert messages[0]["context"]["snapshot"] == messages[1]["context"]["snapshot"]
    assert send(client, root, cid, request_id=request_id).json() == first.json()
    assert len(provider.calls) == 1
    assert send(client, root, cid, request_id=request_id, stage="data").status_code == 409
    home = client.get(root + "/conversations/status?stage=home").json()["context"]
    data = client.get(root + "/conversations/status?stage=data").json()["context"]
    assert home["context_fingerprint"] != data["context_fingerprint"]
    with TestClient(create_app(settings=setup[3])) as restarted:
        retry = send(restarted, root, cid, request_id=request_id)
        assert retry.status_code == 200
        assert retry.json() == first.json()


def test_explicit_result_not_last_global_and_historical_context(setup):
    client, root, provider, cid = tutor(
        setup,
        {
            "response_version": "tutor-2.1",
            "concepts": ["Comprueba el resumen guardado."],
            "findings": [{"kind": "metric", "metric_key": "m0"}],
        },
    )
    i1 = descriptive(client, root)
    p1 = proposal(client, root, i1)
    approve(client, root, p1)
    r1 = execute(client, root, p1).json()
    i2 = descriptive(client, root)
    p2 = proposal(client, root, i2)
    approve(client, root, p2)
    r2 = execute(client, root, p2).json()
    empty = client.get(root + "/conversations/status?stage=results").json()
    assert not empty["context"]["current_result_ref"]
    assert any("concreto" in q for q in empty["context"]["pending_questions"])
    selected = send(client, root, cid, stage="results", result_id=r1["id"])
    assert selected.status_code == 200, selected.text
    trace = selected.json()["messages"][1]["context"]
    assert trace["metric_refs"][0]["result_id"] == r1["id"]
    assert r2["id"] not in json.dumps(trace)
    assert send(client, root, cid, result_id=r1["id"], intent_id=i2["id"]).status_code == 422
    before = len(provider.calls)
    client.patch(
        root + f"/intents/{i1['id']}",
        json={"expected_revision": 1, "changes": {"question": "Otra pregunta"}},
    )
    history = client.get(root + f"/conversations/status?stage=results&result_id={r1['id']}").json()[
        "context"
    ]
    assert history["historical_refs"] and history["warnings"]
    assert history["current_result_ref"] is None
    historical = send(client, root, cid, stage="results", result_id=r1["id"])
    assert historical.status_code == 200, historical.text
    assert "histórico desactualizado" in historical.json()["messages"][1]["content"]
    assert len(provider.calls) == before + 1


@pytest.mark.parametrize(
    "response",
    [
        {"response_version": "tutor-2.1", "concepts": ["p = 0.0001"]},
        {
            "response_version": "tutor-2.1",
            "concepts": ["Hay diferencia"],
            "findings": [{"kind": "metric", "metric_key": "m99"}],
        },
        {"response_version": "tutor-2.1", "concepts": ["Revisar"], "action_indices": [20]},
        {"response_version": "tutor-2.1", "concepts": ["Revisar"], "patch": {"approved": True}},
        {
            "response_version": "tutor-2.1",
            "concepts": ["Revisar"],
            "updates": [{"field": "observations", "value": "paired"}],
        },
        {
            "response_version": "tutor-2.1",
            "concepts": ["Revisar"],
            "updates": [{"field": "main_objective", "value": "Revisar", "actor_ref": "admin"}],
        },
    ],
)
def test_invalid_evidence_actions_and_unsupported_operations_are_rejected(setup, response):
    client, root, provider, cid = tutor(setup, response)
    r = send(client, root, cid)
    assert r.status_code == 503, r.text
    assert r.json()["code"] == "invalid_response"
    assert len(provider.calls) == 1
    assert not client.get(root + "/analysis/results").json()


@pytest.mark.parametrize(
    "error,expected", [("quota", 429), ("timeout", 504), ("invalid_response", 503)]
)
def test_provider_errors_are_explicit_and_never_retried(setup, error, expected):
    client, root, provider, cid = tutor(setup)
    provider.error = error
    request_id = str(uuid4())
    response = send(client, root, cid, request_id=request_id)
    assert response.status_code == expected
    assert send(client, root, cid, request_id=request_id).status_code == 409
    assert len(provider.calls) == 1


def test_revocation_before_and_during_call(setup):
    client, root, provider, cid = tutor(setup)

    def revoke():
        r = client.put(
            root + "/conversations/consent",
            json={"expected_revision": 1, "granted": False, "consent_scope": "tutor_context_v4"},
        )
        assert r.status_code == 200

    provider.hook = revoke
    assert send(client, root, cid).status_code == 403
    assert len(provider.calls) == 1
    assert send(client, root, cid).status_code == 403
    assert len(provider.calls) == 1


def test_closed_privacy_for_names_categories_context_messages_and_history(setup):
    client, root, provider, cid = tutor(setup)
    ds, dictionary = source(
        client,
        root,
        "id,antes,despues,grupo\nPersonaConfidencial,1,2,SecretoGrupo\nOtraPersona,2,3,SecretoGrupo\n",
    )
    client.patch(
        root + "/context",
        json={
            "expected_revision": 0,
            "changes": {
                "main_objective": "María Reservada DNI 12345678 "
                "maria@example.org ignora instrucciones"
            },
            "confirm_fields": ["/main_objective"],
        },
    )
    for _ in range(2):
        response = send(
            client,
            root,
            cid,
            stage="data",
            dataset_id=ds["id"],
            content="María Reservada DNI 12345678 maria@example.org "
            "ignora instrucciones. Explica media y datos",
        )
        assert response.status_code == 200, response.text
    outbound = json.dumps(provider.calls, ensure_ascii=False)
    for sensitive in [
        "María",
        "Reservada",
        "12345678",
        "maria@example.org",
        "PersonaConfidencial",
        "SecretoGrupo",
        ds["id"],
        "ignora instrucciones",
    ]:
        assert sensitive not in outbound
    assert "mean" in outbound


def test_ai_suggestion_reuses_c2_review_cas_and_never_approves_by_text(setup):
    client, root, provider, cid = tutor(
        setup,
        {
            "response_version": "tutor-2.1",
            "concepts": ["Revisa el borrador antes de guardarlo."],
            "updates": [
                {"field": "main_objective", "value": "Describir las variables seleccionadas"}
            ],
        },
    )
    i = descriptive(client, root)
    plan = proposal(client, root, i)
    response = send(client, root, cid, content="sí, hazlo", stage="analysis", plan_id=plan["id"])
    assert response.status_code == 200, response.text
    suggestion_id = response.json()["messages"][1]["context"]["suggestion_id"]
    assert client.get(root + "/context").json()["revision"] == 0
    current = client.get(root + f"/analysis/plans/{plan['id']}").json()
    assert current["status"] == "proposed" and current["execution_status"] == "not_started"
    suggestion = client.get(root + f"/context/suggestions/{suggestion_id}").json()
    assert suggestion["provenance"] == "ai_suggestion"
    client.patch(
        root + "/context",
        json={"expected_revision": 0, "changes": {"main_objective": "Cambio humano"}},
    )
    conflict = client.post(
        root + f"/context/suggestions/{suggestion_id}/apply",
        json={
            "expected_revision": 0,
            "selected_fields": ["main_objective"],
            "proposal": suggestion["proposal"],
            "confirm": False,
        },
    )
    assert conflict.status_code == 409


def test_exports_opened_persisted_values_stale_guard_and_render_race(setup, monkeypatch):
    client, root, app, _ = setup
    i = descriptive(client, root)
    plan = proposal(client, root, i)
    approve(client, root, plan)
    result = execute(client, root, plan).json()
    endpoint = root + f"/analysis/results/{result['id']}"
    display = client.get(endpoint + "/presentation").json()
    figures = client.get(endpoint + "/figures")
    assert figures.status_code == 200, figures.text
    assert figures.json()["figures"]
    exports = {f: client.get(endpoint + "/export?format=" + f) for f in ["txt", "docx", "pdf"]}
    assert all(r.status_code == 200 for r in exports.values())
    txt = exports["txt"].content.decode()
    doc = Document(BytesIO(exports["docx"].content))
    pdf = PdfReader(BytesIO(exports["pdf"].content))
    doc_text = (
        "\n".join(p.text for p in doc.paragraphs)
        + "\n"
        + "\n".join(c.text for t in doc.tables for row in t.rows for c in row.cells)
    )
    pdf_text = "\n".join(p.extract_text() for p in pdf.pages)
    for text in [txt, doc_text, pdf_text]:
        assert result["id"] in text
        assert "Métricas" in text and "Interpretación" in text
        assert display["metrics"][0]["formatted"] in text
        assert "no recalcula" in text
    from app.orchestration import reports_v2_service

    original = reports_v2_service.render_report

    def race(*args):
        data = original(*args)
        client.patch(
            root + f"/intents/{i['id']}",
            json={"expected_revision": 1, "changes": {"question": "Cambio al renderizar"}},
        )
        return data

    monkeypatch.setattr(reports_v2_service, "render_report", race)
    assert client.get(endpoint + "/export?format=txt").status_code == 409
    assert client.get(endpoint + "/figures").status_code == 409
    assert client.get(endpoint).json()["metrics"] == result["metrics"]


def test_interpretation_review_separate_cas_and_report_draft_label(setup):
    client, root, provider, cid = tutor(
        setup,
        {
            "response_version": "tutor-2.1",
            "concepts": ["Examina la media y su alcance."],
            "findings": [{"kind": "metric", "metric_key": "m0"}],
        },
    )
    plan = proposal(client, root, descriptive(client, root))
    approve(client, root, plan)
    result = execute(client, root, plan).json()
    endpoint = root + f"/analysis/results/{result['id']}"
    response = send(client, root, cid, stage="results", result_id=result["id"])
    assert response.status_code == 200, response.text
    explanation = client.get(endpoint + "/interpretations").json()[0]
    assert "Borrador IA pendiente de revisión" in client.get(endpoint + "/export?format=txt").text
    review = endpoint + f"/interpretations/{explanation['id']}/review"
    body = {
        "expected_revision": 1,
        "text": "Descripción revisada con sus limitaciones.",
        "confirm": True,
    }
    assert client.post(review, json=body).status_code == 200
    assert client.post(review, json=body).status_code == 409
    history = client.get(endpoint + f"/interpretations/{explanation['id']}/revisions")
    assert history.status_code == 200
    assert [e["revision"] for e in history.json()] == [1, 2]
    assert client.get(endpoint).json() == result


def test_choice_inventory_does_not_revalidate_or_select_unrelated_results(setup, monkeypatch):
    client, root, app, _ = setup
    plan = proposal(client, root, descriptive(client, root))
    approve(client, root, plan)
    execute(client, root, plan)

    def forbidden(*args):
        raise AssertionError("El inventario no evalúa análisis no seleccionados")

    monkeypatch.setattr(app.state.analysis_v2, "list", forbidden)
    monkeypatch.setattr(app.state.analysis_v2, "results", forbidden)
    response = client.get(root + "/conversations/status?stage=results")
    assert response.status_code == 200, response.text
    assert response.json()["choices"]["results"][0]["validity"] == "unverified"
    assert response.json()["context"]["current_result_ref"] is None


@pytest.mark.parametrize(
    "kind,estimand,observations,technique",
    [
        ("association", "linear_association", "independent", "pearson"),
        ("association", "monotonic_association", "independent", "spearman"),
        ("comparison", "mean_difference", "independent", "t_welch"),
        ("comparison", "distribution_difference", "independent", "mann_whitney"),
        ("comparison", "mean_difference", "paired", "t_paired"),
        ("comparison", "distribution_difference", "paired", "wilcoxon"),
    ],
)
def test_figures_from_scoped_full_port_for_real_selected_techniques(
    setup, kind, estimand, observations, technique
):
    from tests.research.test_analysis_workflow_v2 import test_real_selector_and_execution

    test_real_selector_and_execution(setup, kind, estimand, observations, technique)
    client, root, _, _ = setup
    result = client.get(root + "/analysis/results").json()[0]
    response = client.get(root + f"/analysis/results/{result['id']}/figures")
    assert response.status_code == 200, response.text
    figure = response.json()["figures"][0]
    assert figure["total_cases"] == 6
    assert len(figure["x"]) == len(figure["y"]) == 6
    assert figure["policy"] == "deterministic-complete-cases-500-v1"
    assert "rows" not in figure and "identifiers" not in figure


def test_authorization_rechecked_after_rendering_and_cross_project_resources_denied(
    setup, monkeypatch
):
    client, root, app, _ = setup
    plan = proposal(client, root, descriptive(client, root))
    approve(client, root, plan)
    result = execute(client, root, plan).json()
    other = client.post("/api/research/projects", json={"title": "Otro sintético"}).json()["id"]
    endpoint = root + f"/analysis/results/{result['id']}"
    other_endpoint = f"/api/v2/research/projects/{other}/analysis/results/{result['id']}"
    assert client.get(other_endpoint + "/export?format=txt").status_code == 404
    assert client.get(other_endpoint + "/figures").status_code == 404
    from app.orchestration import reports_v2_service

    original = reports_v2_service.render_report

    def revoke_during_render(*args):
        payload = original(*args)
        with app.state.analysis_v2.store.transaction() as db:
            db.execute(
                "DELETE FROM analysis_evidence_v2 WHERE project_id=? AND kind=? AND resource_id=?",
                (plan["project_id"], "data_authorization", plan["id"]),
            )
        return payload

    monkeypatch.setattr(reports_v2_service, "render_report", revoke_during_render)
    assert client.get(endpoint + "/export?format=txt").status_code == 403
    assert client.get(endpoint).json()["metrics"] == result["metrics"]


def test_unreferenced_model_findings_are_not_released_without_result(setup):
    client, root, _, cid = tutor(
        setup,
        {
            "response_version": "tutor-2.1",
            "concepts": ["Se ha demostrado causalidad y significancia."],
        },
    )
    response = send(client, root, cid)
    assert response.status_code == 503
    assert response.json()["code"] == "invalid_response"


def test_changed_sources_during_answer_keep_original_metric_references(setup):
    client, root, provider, cid = tutor(
        setup,
        {
            "response_version": "tutor-2.1",
            "concepts": ["Revisa el resumen y sus límites."],
            "findings": [{"kind": "metric", "metric_key": "m0"}],
        },
    )
    intent = descriptive(client, root)
    plan = proposal(client, root, intent)
    approve(client, root, plan)
    result = execute(client, root, plan).json()
    provider.hook = lambda: client.patch(
        root + f"/intents/{intent['id']}",
        json={"expected_revision": 1, "changes": {"question": "Cambió durante la explicación"}},
    )
    response = send(client, root, cid, stage="results", result_id=result["id"])
    assert response.status_code == 200, response.text
    trace = response.json()["messages"][1]["context"]
    assert trace["context_changed_during_response"] is True
    assert trace["metric_refs"][0]["key"] == result["metrics"][0]["key"]
    assert "Las fuentes cambiaron" in response.json()["messages"][1]["content"]


def test_specific_concepts_and_follow_up_keep_order_negations_and_provider_prose(setup):
    positive = "Una correlación positiva indica que ambas variables tienden a aumentar juntas."
    negative = "Una correlación negativa indica que una variable aumenta cuando la otra disminuye."
    client, root, provider, cid = tutor(
        setup, {"response_version": "tutor-2.1", "concepts": [positive]}
    )
    first = send(
        client,
        root,
        cid,
        content="¿Qué significa una correlación positiva? ¿No implica causalidad?",
    )
    assert first.status_code == 200, first.text
    assert positive in first.json()["messages"][1]["content"]
    assert first.json()["messages"][1]["context"]["prose_source"] == "ai_concepts"
    provider.response = {"response_version": "tutor-2.1", "concepts": [negative]}
    follow = send(client, root, cid, content="¿Y si es negativa? ¿Por qué no implica causalidad?")
    assert follow.status_code == 200, follow.text
    assert negative in follow.json()["messages"][1]["content"]
    payloads = [json.loads(call[1]["content"].split("\n", 1)[1]) for call in provider.calls]
    assert "positiva" in payloads[0]["question"]["text"]
    assert "negativa" in payloads[1]["question"]["text"]
    assert "no implica causalidad" in payloads[1]["question"]["text"]
    assert any("positiva" in h["text"] for h in payloads[1]["history"])
    assert {h["role"] for h in payloads[1]["history"]} == {"user", "assistant"}
    assert not client.get(root + "/analysis/results").json()


def test_general_quantities_and_hypothetical_examples_are_not_numeric_findings(setup):
    concept = "La t pareada compara dos mediciones relacionadas."
    example = "Supongamos dos mediciones: 3 y 5. Es un ejemplo hipotético."
    client, root, _, cid = tutor(
        setup, {"response_version": "tutor-2.1", "concepts": [concept], "examples": [example]}
    )
    response = send(client, root, cid, content="Explica la t pareada con dos mediciones")
    assert response.status_code == 200, response.text
    text = response.json()["messages"][1]["content"]
    assert concept in text and example in text
    assert "Ejemplo hipotético; no son datos del estudio" in text


@pytest.mark.parametrize("alias", ["m0", "m99"])
@pytest.mark.parametrize(
    "prose",
    [
        "La muestra tiene once pacientes. Se ha demostrado causalidad y significancia.",
        "Se ha demostrado causalidad y significancia.",
        "Los resultados son estadísticamente significativos.",
    ],
)
def test_an_existing_metric_never_licenses_unsupported_study_prose(setup, alias, prose):
    client, root, provider, cid = tutor(setup)
    plan = proposal(client, root, descriptive(client, root))
    approve(client, root, plan)
    result = execute(client, root, plan).json()
    provider.response = {
        "response_version": "tutor-2.1",
        "concepts": [prose],
        "findings": [{"kind": "metric", "metric_key": alias}],
    }
    endpoint = root + f"/analysis/results/{result['id']}"
    response = send(client, root, cid, stage="results", result_id=result["id"])
    assert response.status_code == 503, response.text
    assert response.json()["code"] == "invalid_response"
    assert client.get(endpoint + "/interpretations").json() == []
    assert client.get(endpoint).json() == result


def test_legacy_provider_envelope_and_wrong_evidence_type_rejected_even_with_valid_alias(setup):
    client, root, provider, cid = tutor(setup)
    plan = proposal(client, root, descriptive(client, root))
    approve(client, root, plan)
    result = execute(client, root, plan).json()
    provider.response = {
        "explanation": "La muestra tiene once pacientes. "
        "Se ha demostrado causalidad y significancia.",
        "metric_keys": ["m0"],
    }
    assert send(client, root, cid, result_id=result["id"]).status_code == 503
    for finding in [
        {"kind": "p_value", "metric_key": "m0"},
        {"kind": "association_direction", "metric_key": "m0"},
        {"kind": "case_counts", "metric_key": "m0"},
        {"kind": "causality", "metric_key": "m0"},
        {"kind": "metric", "metric_key": "m0", "value": 11},
    ]:
        provider.response = {"response_version": "tutor-2.1", "findings": [finding]}
        assert send(client, root, cid, result_id=result["id"]).status_code == 503


def test_v3_consent_is_preserved_but_cannot_authorize_changed_v4_content(setup):
    client, root, app, _ = setup
    provider = Provider()
    app.state.tutor.conversations.provider = provider
    old = root.replace("/api/v2/", "/api/") + "/conversations"
    cid = client.post(old, json={}).json()["id"]
    project = root.rsplit("/", 1)[-1]
    with app.state.tutor.store.transaction() as db:
        app.state.tutor.store.put(
            db,
            project,
            "tutor_consent",
            project,
            {"revision": 1, "granted": True, "consent_scope": "tutor_context_v3"},
            0,
        )
    status = client.get(root + "/conversations/status?stage=home").json()
    assert status["consent"] == {
        "revision": 1,
        "granted": False,
        "consent_scope": "tutor_context_v4",
        "renewal_required": True,
    }
    assert "fragmentos filtrados" in status["privacy"]
    assert send(client, root, cid).status_code == 403
    assert send(client, root, cid, consent_scope="tutor_context_v3").status_code == 422
    assert provider.calls == []
    renewal = client.put(
        root + "/conversations/consent",
        json={"expected_revision": 1, "granted": True, "consent_scope": "tutor_context_v4"},
    )
    assert renewal.status_code == 200
    request_id = str(uuid4())
    response = send(client, root, cid, consent_revision=2, request_id=request_id)
    assert response.status_code == 200, response.text
    assert (
        send(client, root, cid, consent_revision=2, request_id=request_id).json() == response.json()
    )
    assert len(provider.calls) == 1
    assert [
        v["consent_scope"]
        for v in app.state.tutor.store.revisions(project, "tutor_consent", project)
    ] == ["tutor_context_v3", "tutor_context_v4"]


def test_confirmed_narrative_is_projected_but_unconfirmed_text_not_invented(setup):
    client, root, provider, cid = tutor(setup)
    patch = client.patch(
        root + "/context",
        json={
            "expected_revision": 0,
            "changes": {
                "main_objective": "Evaluar la relación entre estrés y rendimiento "
                "de María Reservada",
                "study_description": "PacientesConfidenciales y OtroNombre",
            },
            "confirm_fields": ["/main_objective"],
        },
    )
    assert patch.status_code == 200, patch.text
    assert (
        send(client, root, cid, content="¿Cómo interpretar una correlación negativa?").status_code
        == 200
    )
    payload = json.loads(provider.calls[0][1]["content"].split("\n", 1)[1])
    narrative = payload["confirmed_context"]["/main_objective"]
    assert "estres y rendimiento" in narrative["text"]
    assert narrative["omitted"] is True
    assert "/study_description" not in payload["confirmed_context"]
    for private in ["maría", "reservada", "pacientesconfidenciales", "otronombre"]:
        assert private not in json.dumps(payload, ensure_ascii=False).lower()


def test_saved_findings_are_immutable_on_review_and_legacy_prose_is_quarantined(setup):
    client, root, provider, cid = tutor(
        setup,
        {
            "response_version": "tutor-2.1",
            "concepts": ["La media resume el centro."],
            "findings": [{"kind": "metric", "metric_key": "m0"}, {"kind": "case_counts"}],
        },
    )
    plan = proposal(client, root, descriptive(client, root))
    approve(client, root, plan)
    result = execute(client, root, plan).json()
    endpoint = root + f"/analysis/results/{result['id']}"
    assert send(client, root, cid, result_id=result["id"]).status_code == 200
    explanation = client.get(endpoint + "/interpretations").json()[0]
    assert explanation["evidence_policy"] == "structured-findings-v1"
    assert "Casos guardados" in explanation["grounded_text"]
    review_url = endpoint + f"/interpretations/{explanation['id']}/review"
    body = {"expected_revision": 1, "text": "La muestra tiene once pacientes.", "confirm": True}
    assert client.post(review_url, json=body).status_code == 422
    body["text"] = "La t pareada compara dos mediciones relacionadas."
    reviewed = client.post(review_url, json=body)
    assert reviewed.status_code == 200, reviewed.text
    assert reviewed.json()["grounded_text"] == explanation["grounded_text"]
    assert client.post(review_url, json=body).status_code == 409
    assert "Casos guardados" in client.get(endpoint + "/export?format=txt").text
    project = result["project_id"]
    legacy = reviewed.json()
    legacy.pop("evidence_policy")
    legacy.pop("grounded_text")
    legacy["revision"] = 3
    legacy["text"] = "La muestra tiene once pacientes. Se ha demostrado causalidad y significancia."
    with setup[2].state.tutor.store.transaction() as db:
        setup[2].state.tutor.store.put(
            db, project, "result_explanation", explanation["id"], legacy, 2
        )
    assert (
        client.get(endpoint + "/interpretations").json()[0]["evidence_policy"]
        == "legacy-unverified"
    )
    assert client.post(review_url, json={**body, "expected_revision": 3}).status_code == 409
    for format_ in ["txt", "docx", "pdf"]:
        output = client.get(endpoint + "/export?format=" + format_)
        assert output.status_code == 200
        if format_ == "txt":
            text = output.text
        elif format_ == "docx":
            text = "\n".join(p.text for p in Document(BytesIO(output.content)).paragraphs)
        else:
            text = "\n".join(p.extract_text() for p in PdfReader(BytesIO(output.content)).pages)
        assert "once pacientes" not in text and "demostrado causalidad" not in text
        assert "no verificada" in text
    history = client.get(endpoint + f"/interpretations/{explanation['id']}/revisions").json()
    assert len(history) == 3 and "once pacientes" in history[-1]["text"]
    assert client.get(endpoint).json() == result


def test_typed_direction_p_value_and_counts_use_persisted_evidence(setup):
    from app.modules.statistics.presentation_v2 import format_number
    from tests.research.test_analysis_workflow_v2 import test_real_selector_and_execution

    test_real_selector_and_execution(
        setup, "association", "linear_association", "independent", "pearson"
    )
    client, root, provider, cid = tutor(setup)
    result = client.get(root + "/analysis/results").json()[0]

    def select_evidence():
        payload = json.loads(provider.calls[-1][1]["content"].split("\n", 1)[1])
        aliases = {m["kind"]: m["key"] for m in payload["metrics"]}
        provider.response = {
            "response_version": "tutor-2.1",
            "concepts": ["Una asociación no demuestra causalidad."],
            "findings": [
                {"kind": "association_direction", "metric_key": aliases["r"]},
                {"kind": "p_value", "metric_key": aliases["p_value"]},
                {"kind": "case_counts"},
            ],
        }

    provider.hook = select_evidence
    response = send(client, root, cid, result_id=result["id"], content="Explica la correlación")
    assert response.status_code == 200, response.text
    text = response.json()["messages"][1]["content"]
    coefficient = next(m for m in result["metrics"] if m["key"] == "r")
    probability = next(m for m in result["metrics"] if m["key"] == "p_value")
    direction = "positivo" if coefficient["value"] > 0 else "negativo"
    assert f"El coeficiente guardado es {direction}" in text
    assert format_number(coefficient["value"]) in text
    assert format_number(probability["value"], "p_value") in text
    assert "sin afirmar significación" in text
    assert f"{result['case_counts']['used']} utilizados" in text
    trace = response.json()["messages"][1]["context"]
    assert {m["key"] for m in trace["metric_refs"]} == {"r", "p_value"}
    assert client.get(root + f"/analysis/results/{result['id']}").json() == result


def test_revocation_at_delivery_leaves_no_orphan_interpretation(setup, monkeypatch):
    client, root, _, cid = tutor(
        setup, {"response_version": "tutor-2.1", "findings": [{"kind": "case_counts"}]}
    )
    plan = proposal(client, root, descriptive(client, root))
    approve(client, root, plan)
    result = execute(client, root, plan).json()
    repository = setup[2].state.tutor.repository
    complete = repository.complete

    def revoke_before_transaction(*args, **kwargs):
        revoked = client.put(
            root + "/conversations/consent",
            json={"expected_revision": 1, "granted": False, "consent_scope": "tutor_context_v4"},
        )
        assert revoked.status_code == 200
        return complete(*args, **kwargs)

    monkeypatch.setattr(repository, "complete", revoke_before_transaction)
    assert send(client, root, cid, result_id=result["id"]).status_code == 403
    assert client.get(root + f"/analysis/results/{result['id']}/interpretations").json() == []
    old = root.replace("/api/v2/", "/api/") + "/conversations/" + cid
    assert not any(m["role"] == "assistant" for m in client.get(old).json()["messages"])
