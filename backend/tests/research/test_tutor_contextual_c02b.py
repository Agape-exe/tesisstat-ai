"""C02 acceptance regressions: meaning, selected evidence and useful orientation."""

import json
from uuid import UUID, uuid4

import pytest

from app.modules.conversation.tutor_grounding import render_contextual_prose, validate_general_prose
from app.modules.conversation.tutor_privacy import project_text
from app.shared.ai_errors import AIError
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
                "possibilities": "Podríamos describir las medidas y, tras aclarar el diseño, "
                "explorar relaciones o comparaciones.",
                "first_step": "Primero revisaría el significado de las medidas elegidas.",
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
