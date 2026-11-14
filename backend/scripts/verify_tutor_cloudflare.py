"""Opt-in C02 acceptance against Cloudflare, in a NEW synthetic-only database.

Run from backend: python -m scripts.verify_tutor_cloudflare --allow-external
  --output-dir ../.cache/c02b/cloudflare
Never opens the local acceptance database, projects, documents or conversations.
"""

import argparse
import json
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient

from app.modules.research.dev_app import ResearchDevSettings, create_app
from app.shared.adapters.cloudflare import CloudflareLanguageModel
from app.shared.tutor_v2 import TutorWireAnswerV1

QUERY = (
    "He cargado mis datos y no sé por dónde empezar. ¿Qué puedo analizar con esta tabla y "
    "qué me recomiendas hacer primero? Explica por qué y pregúntame lo necesario antes "
    "de preparar una propuesta."
)


def verify(output):
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    settings = ResearchDevSettings(
        _env_file=Path(__file__).resolve().parents[1] / ".env",
        research_db_path=output / "synthetic.sqlite3",
        research_datasets_path=output / "datasets",
        research_documents_path=output / "documents",
    )
    app = create_app(settings=settings)
    provider = app.state.tutor.conversations.provider
    assert isinstance(provider, CloudflareLanguageModel) and provider.configured
    original = provider.chat
    report = {
        "synthetic_only": True,
        "consent_scope": "tutor_context_v5",
        "query": QUERY,
        "provider_calls": 0,
        "cases": [],
        "complete": False,
    }
    current = {}

    def checked(messages, *, max_tokens, **kwargs):
        assert report["provider_calls"] < 2
        serialized = json.dumps(messages, ensure_ascii=False)
        for private in current["denied"]:
            assert private not in serialized
        payload = json.loads(messages[1]["content"].split("\n", 1)[1])
        assert payload["question"] == {"text": QUERY, "omitted": False}
        assert messages[-1] == {"role": "user", "content": QUERY}
        assert not payload["metrics"]
        assert not payload["history"]
        assert any(v.get("detected_type") == "numérico" for v in payload["data"])
        assert (
            payload["confirmed_context"]
            if current["with_context"]
            else not payload["confirmed_context"]
        )
        assert all("source_ref" not in f for f in payload["evidence"])
        assert '"rows": [' not in serialized and '"records":' not in serialized
        report["provider_calls"] += 1
        raw = original(messages, max_tokens=max_tokens, **kwargs)
        (output / f"response-{current['name']}.json").write_text(raw, encoding="utf-8")
        (output / f"outbound-{current['name']}.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        answer = TutorWireAnswerV1.model_validate_json(raw).as_answer()
        assert answer.orientation is not None, "La respuesta vuelve a dar conceptos sin orientación"
        # Do not equate usefulness with one preferred word (e.g. "describir").
        # The full answers remain in evidence.json for the semantic review.
        assert not answer.findings and not answer.examples and not answer.updates
        assert "?" in answer.orientation.clarification
        concrete_topic = any(
            cue in answer.orientation.clarification.casefold()
            for cue in ("fila", "unidad", "persona", "medici", "mismo", "representa", "grupo")
        )
        named_variable = any(
            v.get("name", "").casefold() in answer.orientation.clarification.casefold()
            for v in payload["data"]
            if v.get("variable")
        )
        assert concrete_topic or named_variable
        assert answer.orientation.basis_keys
        selected = [f for f in payload["evidence"] if f["key"] in answer.orientation.basis_keys]
        assert len(selected) == len(set(answer.orientation.basis_keys))
        if current["with_context"]:
            assert any(f["kind"] == "confirmed" for f in selected)
        else:
            assert any(f["kind"] == "detected" and "numérico" in f["text"] for f in selected)
        current["answer"] = answer
        current["payload"] = payload
        return raw

    provider.chat = checked
    try:
        with TestClient(app) as client:
            for with_context in (False, True):
                name = "con-contexto" if with_context else "sin-contexto"
                current.clear()
                current.update(name=name, with_context=with_context)
                project = client.post(
                    "/api/research/projects", json={"title": "ProyectoSinteticoPrivadoC02B"}
                ).json()["id"]
                api = f"/api/v2/research/projects/{project}"
                imported = client.post(
                    api + "/files",
                    content=(
                        b"id,tension_previa,tension_posterior,grupo\n"
                        b"PersonaPrivadaC02B,120,115,TratamientoPrivado\n"
                        b"OtraPersonaPrivadaC02B,125,119,TratamientoPrivado\n"
                        b"TerceraPersonaPrivadaC02B,118,,ControlPrivado\n"
                        b"CuartaPersonaPrivadaC02B,130,127,ControlPrivado\n"
                    ),
                    headers={"X-File-Name": "archivo-privado-c02b.csv"},
                )
                assert imported.status_code == 201, imported.text
                table = imported.json()["sheets"][0]["table_id"]
                current["denied"] = [
                    project,
                    table,
                    "PersonaPrivadaC02B",
                    "OtraPersonaPrivadaC02B",
                    "TerceraPersonaPrivadaC02B",
                    "CuartaPersonaPrivadaC02B",
                    "TratamientoPrivado",
                    "ControlPrivado",
                    "archivo-privado-c02b.csv",
                    "ProyectoSinteticoPrivadoC02B",
                ]
                if with_context:
                    context = client.patch(
                        api + "/context",
                        json={
                            "expected_revision": 0,
                            "changes": {
                                "main_objective": "Evaluar el cambio de tensión arterial "
                                "tras una intervención, "
                                "sin afirmar causalidad a partir de la tabla."
                            },
                            "confirm_fields": ["/main_objective"],
                        },
                    )
                    assert context.status_code == 200, context.text
                    dataset = client.get(api + "/data-tables").json()[0]
                    dictionary = client.get(api + f"/data-tables/{table}/dictionary").json()
                    variable = dictionary["variables"][1]["id"]
                    changed = client.patch(
                        api + f"/data-tables/{table}/dictionary",
                        json={
                            "expected_revision": 0,
                            "dataset_revision": 1,
                            "dataset_hash": dataset["hash"],
                            "changes": {
                                variable: {
                                    "description": "Tensión arterial sistólica previa en mmHg",
                                    "measurement_scale": "ratio",
                                }
                            },
                            "confirm_fields": [
                                f"/variables/{variable}/description",
                                f"/variables/{variable}/measurement_scale",
                            ],
                        },
                    )
                    assert changed.status_code == 200, changed.text
                cid = client.post(
                    f"/api/research/projects/{project}/conversations", json={}
                ).json()["id"]
                consent = client.put(
                    api + "/conversations/consent",
                    json={
                        "expected_revision": 0,
                        "granted": True,
                        "consent_scope": "tutor_context_v5",
                    },
                )
                assert consent.status_code == 200
                body = {
                    "stage": "data",
                    "dataset_id": table,
                    "content": QUERY,
                    "request_id": str(uuid4()),
                    "external_ai_consent": True,
                    "consent_scope": "tutor_context_v5",
                    "consent_revision": 1,
                }
                response = client.post(api + f"/conversations/{cid}/messages", json=body)
                case = {"name": name, "status": response.status_code}
                report["cases"].append(case)
                assert response.status_code == 200, response.text
                message = response.json()["messages"][-1]
                trace = message["context"]
                assert trace["provider_kind"] == "cloudflare_workers_ai"
                assert trace["prose_source"] == "ai_guidance" and trace["evidence_refs"]
                assert (
                    "{{" not in message["content"] and "Concepto general" not in message["content"]
                )
                assert not client.get(api + "/intents").json()
                assert not client.get(api + "/analysis/plans").json()
                assert not client.get(api + "/analysis/results").json()
                calls = report["provider_calls"]
                assert (
                    client.post(api + f"/conversations/{cid}/messages", json=body).json()
                    == response.json()
                )
                assert report["provider_calls"] == calls
                case.update(
                    answer=message["content"],
                    orientation=current["answer"].orientation.model_dump(),
                    question_preserved=True,
                    contract_valid=True,
                    useful_orientation=True,
                    clarification_concrete=True,
                    evidence_kinds=sorted({f["kind"] for f in trace["evidence_refs"]}),
                    no_mutations=True,
                    retry_without_new_call=True,
                )
        report["complete"] = True
    finally:
        (output / "evidence.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--allow-external", action="store_true", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    verify(args.output_dir)
