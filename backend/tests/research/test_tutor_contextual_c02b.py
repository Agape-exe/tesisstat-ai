"""C02 acceptance regressions: meaning, selected evidence and useful orientation."""

import json
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from app.modules.conversation.tutor_grounding import render_contextual_prose, validate_general_prose
from app.modules.conversation.tutor_orientation import option_indices, render_step
from app.modules.conversation.tutor_privacy import outbound_context, project_text
from app.shared.ai_errors import AIError
from app.shared.tutor_v2 import TutorWireAnswerV1
from tests.research.test_analysis_workflow_v2 import approve, descriptive, execute, proposal
from tests.research.test_diagnostics_v2 import setup as setup
from tests.research.test_diagnostics_v2 import source
from tests.research.test_tutor_v2 import send, tutor

ACCEPTANCE_QUERY = (
    "He cargado mis datos y no sé por dónde empezar. ¿Qué puedo analizar con esta tabla y "
    "qué me recomiendas hacer primero? Explica por qué y pregúntame lo necesario antes "
    "de preparar una propuesta."
)


@pytest.mark.parametrize(
    "text",
    [
        ACCEPTANCE_QUERY,
        "No presupongas equivalencia metrológica ni homocedasticidad. ¿Qué aclararías primero?",
        "Analizo conductividad y adsorción: no asumas que las réplicas son sujetos independientes.",
        "¿La prueba de Mann Whitney contrasta medianas? "
        "Explica sus limitaciones sin simplificarlas.",
        "El umbral es 0.05, pero no lo uses para escoger el método. Quiero un IC del 95%.",
        '¿Qué significa "unidad experimental" y cómo afecta al pseudorreplicado?',
        "Evaluar adsorción, sin presumir causalidad.\n"
        "Describir las réplicas, conservando su unidad experimental.",
        "¿Cómo describir puntuacion_satisfaccion_laboral_pretest_2026 sin asumir causalidad?",
        "Comparar Rendimiento Académico y Puntuación Total, sin asumir independencia.",
        "Explorar Electroadsorción Fotoelectrocatalítica con unidades por confirmar.",
    ],
)
def test_selective_projection_preserves_full_nonpersonal_meaning(text):
    assert project_text(text) == {"text": text, "omitted": False}


def test_projection_removes_identifiers_secrets_and_known_local_names_without_erasing_question():
    query = (
        "María Reservada DNI 12345678 maria@example.org token=synthetic-secret-value "
        "https://private.invalid/a; PacienteUnico. ¿Debo revisar el pseudorreplicado primero?"
    )
    projected = project_text(query, private_terms={"PacienteUnico"})
    assert projected["omitted"]
    for private in (
        "María",
        "Reservada",
        "12345678",
        "maria@example.org",
        "synthetic-secret-value",
        "private.invalid",
        "PacienteUnico",
    ):
        assert private not in projected["text"]
    assert "¿Debo revisar el pseudorreplicado primero?" in projected["text"]


def test_opaque_credentials_are_removed_without_classifying_variable_codes_as_secrets():
    token = "aB7kP2zQ9mT4wF6rH8sV3xN5cL1dJ0yG"
    safe = project_text(token + " ¿Cómo describir puntuacion_satisfaccion_laboral_pretest_2026?")
    assert token not in safe["text"]
    assert "puntuacion_satisfaccion_laboral_pretest_2026" in safe["text"]


def test_pasted_observations_never_cross_text_projection():
    value = project_text(
        "¿Cómo empiezo?\nid,medida\nPersonaPrivada,2\nOtraPersona,7\nNo asumas independencia."
    )
    assert value["omitted"] and "Persona" not in value["text"]
    assert "¿Cómo empiezo?" in value["text"] and "No asumas independencia." in value["text"]


def test_nested_json_records_are_removed_as_a_whole_without_erasing_the_question():
    value = project_text(
        '¿Cómo empiezo? [{"rows":[{"nombre":"NombrePrivado"}]},'
        '{"contacto":"OtroPrivado"}] No asumas independencia.'
    )
    assert "Privado" not in value["text"]
    assert "¿Cómo empiezo?" in value["text"] and "No asumas independencia." in value["text"]


@pytest.mark.parametrize(
    "secret",
    [
        '"token": "abc 123"',
        "contraseña es privada123",
        "api_key='valor con espacios'",
        "-----BEGIN PRIVATE KEY-----\nvalor-privado\n-----END PRIVATE KEY-----",
    ],
)
def test_credential_formats_are_removed_without_suppressing_statistical_text(secret):
    query = secret + '\nExplica "unidad experimental" sin asumir independencia.'
    safe = project_text(query)
    assert safe["omitted"]
    for value in ("abc 123", "privada123", "valor con espacios", "valor-privado"):
        assert value not in safe["text"]
    assert 'Explica "unidad experimental" sin asumir independencia.' in safe["text"]


def test_v4_acceptance_conversation_is_preserved_and_not_retransmitted_under_v5(setup):
    client, root, provider, cid = tutor(setup)
    repository = setup[2].state.tutor.repository
    snapshot = client.get(root + "/conversations/status?stage=home").json()["context"][
        "context_fingerprint"
    ]
    trace = {"snapshot": snapshot, "consent_scope": "tutor_context_v4"}
    request = uuid4()
    repository.claim(UUID(cid), request, "ConsultaPrivadaDeAceptacion", 45, context=trace)
    repository.complete(UUID(cid), request, "RespuestaAnteriorDeAceptacion", trace)
    assert send(client, root, cid, content="¿Por dónde comienzo?").status_code == 200
    payload = json.loads(provider.calls[0][1]["content"].split("\n", 1)[1])
    assert not payload["history"] and payload["history_omitted"]
    old = root.replace("/api/v2/", "/api/") + "/conversations/" + cid
    saved = client.get(old).json()["messages"]
    assert [m["content"] for m in saved[:2]] == [
        "ConsultaPrivadaDeAceptacion",
        "RespuestaAnteriorDeAceptacion",
    ]


def test_provider_budget_counts_schema_and_bounds_whole_variable_facts_not_query_words(setup):
    client, root, _, _ = setup
    names = [f"medida{n}" for n in range(30)]
    csv = (
        ",".join(names)
        + "\n"
        + ",".join("2" for _ in names)
        + "\n"
        + ",".join("4" for _ in names)
        + "\n"
    )
    dataset, _ = source(client, root, csv)
    client, root, provider, cid = tutor(setup)
    response = send(
        client, root, cid, stage="data", dataset_id=dataset["id"], content=ACCEPTANCE_QUERY
    )
    assert response.status_code == 200, response.text
    payload = json.loads(provider.calls[0][1]["content"].split("\n", 1)[1])
    assert payload["question"] == {"text": ACCEPTANCE_QUERY, "omitted": False}
    assert payload["summary_facts_omitted"] > 0
    assert len(payload["data"]) >= 3
    assert response.json()["messages"][1]["context"]["summary_facts_omitted"] > 0
    specific = ACCEPTANCE_QUERY + " Detalla medida29."
    assert (
        send(
            client, root, cid, stage="data", dataset_id=dataset["id"], content=specific
        ).status_code
        == 200
    )
    payload = json.loads(provider.calls[-1][1]["content"].split("\n", 1)[1])
    assert payload["question"]["text"] == specific
    assert any(v.get("name") == "medida29" for v in payload["data"])
    assert set(payload["orientation_brief"]["priority_basis_keys"]) <= {
        f["key"] for f in payload["evidence"]
    }


def test_legitimate_recommendations_are_not_confused_with_empirical_findings():
    assert validate_general_prose(
        "¿Tus datos contienen mediciones repetidas de las mismas unidades?"
    )
    assert not validate_general_prose("Los resultados son significativos. ¿Qué significan?")
    assert validate_general_prose(
        "Para revisar los datos, la dispersión muestra cuánto varía una medida."
    )
    assert validate_general_prose(
        "Primero revisaría el significado de las columnas antes de comparar."
    )
    for claim in (
        "Los resultados son estadísticamente significativos.",
        "La tabla tiene 999 registros.",
        "Las variables son numéricas.",
    ):
        assert not validate_general_prose(claim)
    with pytest.raises(AIError):
        render_contextual_prose("La tabla tiene 999 registros. {{f0}}", [])
    with pytest.raises(AIError):
        render_contextual_prose("Las mediciones de {{f0}} se podrían describir.", [])


def test_safe_summary_uses_detection_and_confirmed_meaning_not_drafts_or_rows(setup):
    client, root, app, _ = setup
    uploaded = client.post(
        root + "/files",
        content=b"id,conductividad,lote\npaciente-secreto,2,A\notro-secreto,4,B\n",
        headers={"X-File-Name": "privado.csv"},
    ).json()
    table = uploaded["sheets"][0]["table_id"]
    before = client.get(root + f"/conversations/status?stage=data&dataset_id={table}").json()[
        "context"
    ]
    numeric = next(v for v in before["data_summary"] if v.get("name") == "conductividad")
    assert numeric["detected_type"] == "numérico"
    assert numeric["scale"] == "unknown" and not numeric["scale_confirmed"]
    dataset = app.state.tutor.analysis.workspace.dataset(root.rsplit("/", 1)[-1], table)
    dictionary = client.get(root + f"/data-tables/{table}/dictionary").json()
    variable = dictionary["variables"][1]["id"]
    patch = {
        "expected_revision": 0,
        "dataset_revision": 1,
        "dataset_hash": dataset.hash,
        "changes": {
            variable: {
                "description": "Conductividad eléctrica en microsiemens",
                "measurement_scale": "ratio",
            }
        },
        "confirm_fields": [
            f"/variables/{variable}/description",
            f"/variables/{variable}/measurement_scale",
        ],
    }
    assert client.patch(root + f"/data-tables/{table}/dictionary", json=patch).status_code == 200
    client.patch(
        root + "/context",
        json={
            "expected_revision": 0,
            "changes": {
                "main_objective": "Examinar adsorción sin asumir causalidad",
                "study_description": "NarrativaEnBorrador",
            },
            "confirm_fields": ["/main_objective"],
        },
    )
    client, root, provider, cid = tutor(setup)
    assert (
        send(
            client, root, cid, stage="data", dataset_id=table, content=ACCEPTANCE_QUERY
        ).status_code
        == 200
    )
    payload = json.loads(provider.calls[0][1]["content"].split("\n", 1)[1])
    assert payload["question"]["text"] == ACCEPTANCE_QUERY
    assert provider.calls[0][-1] == {"role": "user", "content": ACCEPTANCE_QUERY}
    assert "query_topics" not in payload and "confirmed_topics" not in payload
    assert (
        payload["confirmed_context"]["/main_objective"]["text"]
        == "Examinar adsorción sin asumir causalidad"
    )
    assert "/study_description" not in payload["confirmed_context"]
    assert any(
        f["kind"] == "confirmed" and "microsiemens" in f["text"] for f in payload["evidence"]
    )
    assert any(
        f["kind"] == "detected" and "conductividad" in f["text"] for f in payload["evidence"]
    )
    outbound = json.dumps(provider.calls, ensure_ascii=False)
    for private in (
        "paciente-secreto",
        "otro-secreto",
        "privado.csv",
        table,
        "NarrativaEnBorrador",
    ):
        assert private not in outbound
    assert not payload["metrics"]


def test_orientation_renders_coherently_from_server_facts_and_does_not_prepare_or_execute(setup):
    client, root, _, _ = setup
    ds, _ = source(client, root)
    client, root, provider, cid = tutor(
        setup,
        {
            "response_version": "tutor-2.2",
            "orientation": {
                "option_indices": [0],
                "next_step": "clarify_observations",
                "reason": "Esto permite elegir un resumen que responda a tu pregunta.",
                "basis_keys": ["f0"],
                "clarification": "¿Cada fila representa una unidad distinta "
                "o una medición repetida de la misma unidad?",
            },
            "action_indices": [0],
        },
    )
    result = send(client, root, cid, stage="data", dataset_id=ds["id"], content=ACCEPTANCE_QUERY)
    assert result.status_code == 200, result.text
    message = result.json()["messages"][1]
    assert "Concepto general" not in message["content"] and "{{" not in message["content"]
    assert "4 registros" in message["content"] and "¿Cada fila" in message["content"]
    trace = message["context"]
    assert trace["prose_source"] == "ai_guidance"
    assert trace["evidence_refs"][0]["source_ref"]["id"] == ds["id"]
    assert trace["evidence_refs"][0]["kind"] == "calculated"
    assert not client.get(root + "/intents").json()
    assert not client.get(root + "/analysis/plans").json()
    assert not client.get(root + "/analysis/results").json()
    provider.response["orientation"]["basis_keys"] = ["f99"]
    invalid = send(client, root, cid, stage="data", dataset_id=ds["id"], content=ACCEPTANCE_QUERY)
    assert invalid.status_code == 503 and invalid.json()["code"] == "invalid_response"


def test_context_facts_in_result_chat_do_not_enter_the_editable_result_prose(setup):
    client, root, _, _ = setup
    plan = proposal(client, root, descriptive(client, root))
    approve(client, root, plan)
    result = execute(client, root, plan).json()
    client, root, _, cid = tutor(
        setup,
        {
            "response_version": "tutor-2.2",
            "concepts": ["{{f0}} Revisa la media junto con la dispersión antes de interpretar."],
            "findings": [{"kind": "metric", "metric_key": "m0"}],
        },
    )
    response = send(client, root, cid, stage="results", result_id=result["id"])
    assert response.status_code == 200, response.text
    assert "La tabla seleccionada contiene" in response.json()["messages"][1]["content"]
    endpoint = root + f"/analysis/results/{result['id']}/interpretations"
    explanation = client.get(endpoint).json()[0]
    assert "La tabla seleccionada contiene" not in explanation["text"]
    reviewed = client.post(
        endpoint + f"/{explanation['id']}/review",
        json={"expected_revision": 1, "text": explanation["text"], "confirm": True},
    )
    assert reviewed.status_code == 200, reviewed.text
    assert reviewed.json()["grounded_text"] == explanation["grounded_text"]


def test_short_local_codes_do_not_erase_negations_or_years():
    safe = project_text(
        "No asumas independencia en 2026. Caso NO; id=2026.", private_terms={"NO", "2026"}
    )
    assert safe["text"].startswith("No asumas independencia en 2026.")
    assert "Caso NO" not in safe["text"] and "id=2026" not in safe["text"]


def test_personal_headers_are_aliased_but_unfamiliar_variable_meanings_survive(setup):
    client, root, _, _ = setup
    ds, _ = source(
        client, root, "María Reservada,Electroadsorción Fotoelectrocatalítica\n2,4\n3,8\n"
    )
    client, root, provider, cid = tutor(setup)
    response = send(
        client,
        root,
        cid,
        stage="data",
        dataset_id=ds["id"],
        content="¿Cómo empiezo con María Reservada y la electroadsorción?",
    )
    assert response.status_code == 200, response.text
    transmitted = json.dumps(provider.calls, ensure_ascii=False)
    assert "María" not in transmitted and "Reservada" not in transmitted
    payload = json.loads(provider.calls[0][1]["content"].split("\n", 1)[1])
    assert any(v.get("name") == "Electroadsorción Fotoelectrocatalítica" for v in payload["data"])
    assert all("variable_id" not in v for v in payload["data"])


def test_metric_aliases_keep_safe_variable_meaning_and_exclude_identifier_metrics():
    context = SimpleNamespace(
        intent_summary={},
        evidence=[],
        stage="results",
        confirmed_summary={},
        source_refs=[],
        historical_refs=[],
        allowed_actions=[],
        data_summary=[
            {"variable_id": "local-id", "variable": "Variable 1", "name": "id", "identifier": True},
            {
                "variable_id": "local-measure",
                "variable": "Variable 2",
                "name": "conductividad",
                "detected_type": "numérico",
                "private_extra": "never-send",
            },
        ],
    )
    result = SimpleNamespace(
        metrics=[
            SimpleNamespace(key="local-id.mean", value=12345678),
            SimpleNamespace(key="local-measure.mean", value=3.5),
        ]
    )
    payload, metric_map = outbound_context(context, result)
    assert payload["metrics"] == [
        {
            "key": "m0",
            "kind": "mean",
            "value": 3.5,
            "variable": "Variable 2",
            "variable_name": "conductividad",
        }
    ]
    assert payload["metrics_omitted"] == 1 and list(metric_map) == ["m0"]
    transmitted = json.dumps(payload)
    for private in ("local-id", "local-measure", "private_extra", "never-send", "12345678"):
        assert private not in transmitted


def test_orientation_rejects_unavailable_analysis_routes_and_result_steps():
    def action(kind):
        return SimpleNamespace(kind=kind, destination="analysis")

    context = SimpleNamespace(
        data_summary=[
            {
                "variable": "Variable 1",
                "name": "grupo",
                "detected_type": "texto",
                "scale": "nominal",
                "scale_confirmed": True,
            }
        ],
        intent_summary={},
        allowed_actions=[
            action("prepare_descriptive"),
            action("start_association"),
            action("start_comparison"),
        ],
        evidence=[],
    )
    assert option_indices(context) == [0]
    with pytest.raises(AIError):
        render_step("review_result", context)


def test_flat_provider_transport_still_enforces_domain_orientation_and_fact_boundaries():
    wire = {
        "response_version": "tutor-wire-1.0",
        "mode": "orientation",
        "text": "Aclarar el significado evita resumir magnitudes incompatibles.",
        "next_step": "review_variables",
        "option_indices": [0],
        "question": "¿Qué representa conductividad en tu estudio?",
        "basis_keys": ["f1"],
    }
    answer = TutorWireAnswerV1.model_validate(wire).as_answer()
    assert answer.response_version == "tutor-2.2" and answer.orientation.basis_keys == ["f1"]
    for changes in (
        {"next_step": "none"},
        {"option_indices": []},
        {"question": "Confirma la escala."},
        {"text": "Considera {{f1}} primero."},
        {"mode": "explanation"},
    ):
        with pytest.raises((ValueError, ValidationError)):
            TutorWireAnswerV1.model_validate({**wire, **changes}).as_answer()
    explanation = {
        **wire,
        "mode": "explanation",
        "next_step": "none",
        "option_indices": [],
        "question": "",
    }
    assert TutorWireAnswerV1.model_validate(explanation).as_answer().concepts == [
        "{{f1}} " + wire["text"]
    ]
