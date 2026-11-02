"""Isolated synthetic demo. No credentials, external transport or model inference."""

import io
import json
from pathlib import Path
from uuid import uuid4

import uvicorn
from docx import Document
from fastapi.testclient import TestClient

from app.modules.conversation.context import normalize
from app.modules.research.dev_app import ResearchDevSettings, create_app


class LocalContextProvider:
    configured = True

    def chat(self, messages, *, max_tokens):
        payload = json.loads(messages[0]["content"].split("\nDATOS_JSON:\n")[1])
        question = normalize(messages[-1]["content"])
        keys, kinds = set(), set()
        if "objetiv" in question:
            keys.update({"general_objective", "specific_objectives"})
        if "hipotes" in question:
            keys.update({"general_hypothesis", "specific_hypotheses"})
        if "variable" in question or "dimension" in question:
            keys.add("variables")
        if any(word in question for word in ("dataset", "datos", "fila", "columna")):
            kinds.update({"dataset", "eda"})
        if "pearson" in question or "resultado" in question:
            kinds.add("result")
        facts = [
            f
            for f in payload["facts"]
            if f["field"].split("[")[0] in keys or f["source"]["kind"] in kinds
        ]
        lines = ["**Simulación local: sin Qwen3 ni conexión externa.**"]
        if not facts:
            lines.append("No hay hechos seleccionados para esta consulta. Revisa las fuentes:")
            lines.append(json.dumps(payload["source_states"], ensure_ascii=False))
        for fact in facts:
            source = fact["source"]
            value = json.dumps(fact["value"], ensure_ascii=False)
            lines.append(
                f"- {fact['field']}: {value} "
                f"(fuente {source['kind']} {source['id']}; {source['status']})."
            )
        if payload["history_may_reference_previous_sources"]:
            lines.append("El historial puede referirse a fuentes anteriores.")
        if payload["omitted_facts"]:
            lines.append("Se omitieron datos por el límite de contexto.")
        return "\n\n".join(lines)


def seed(app):
    """Use normal HTTP workflows, including explicit approval outside the chat."""
    client = TestClient(app)
    if client.get("/api/research/projects").json():
        return

    def request(method, path, **kwargs):
        result = client.request(method, path, **kwargs)
        result.raise_for_status()
        return result.json()

    def finding(text):
        return {"value": text, "kind": "manual", "evidence": []}

    for index in (1, 2):
        project = request(
            "POST",
            "/api/research/projects",
            json={
                "title": f"Demostración sintética {index}: horas y rendimiento",
                "university": "Universidad ficticia",
                "program": "Programa ficticio",
                "degree": "bachelor",
            },
        )
        root = f"/api/research/projects/{project['id']}"
        if index == 2:
            continue  # Empty project for isolation/missing-source checks.
        doc = Document()
        doc.add_paragraph("Documento enteramente ficticio para validación local.")
        buffer = io.BytesIO()
        doc.save(buffer)
        document = request(
            "POST",
            root + "/documents",
            content=buffer.getvalue(),
            headers={"X-File-Name": "sintetico.docx"},
        )
        document_root = root + f"/documents/{document['id']}"
        review = request("POST", document_root + "/methodology/review")
        content = review["content"]
        content.update(
            title=finding(project["title"]),
            general_objective=finding("Relacionar horas de estudio y rendimiento ficticios"),
            general_hypothesis=finding("Existe asociación entre horas y rendimiento ficticios"),
            research_design=finding("Observacional transversal"),
        )
        ids = [str(uuid4()), str(uuid4())]
        columns = ["horas", "rendimiento"]
        content["variables"] = [
            {
                "id": vid,
                "name": finding(name),
                "role": finding(role),
                "measurement_scale": finding("ratio"),
                "dimensions": [finding("Dimensión ficticia")],
                "indicators": [],
                "instrument_items": [],
            }
            for vid, name, role in zip(ids, columns, ["independent", "dependent"], strict=True)
        ]
        review = request(
            "PUT",
            document_root + "/methodology/review",
            json={"version": review["version"], "content": content},
        )
        request(
            "POST",
            document_root + "/methodology/review/confirm",
            json={"version": review["version"]},
        )
        dataset = request(
            "POST",
            root + "/datasets",
            content=b"horas,rendimiento\n1,2\n2,4\n3,6\n4,8\n",
            headers={"X-File-Name": "sintetico.csv"},
        )
        dataset_root = root + f"/datasets/{dataset['id']}"
        request("PUT", dataset_root + "/origin", json={"synthetic": True})
        request("POST", dataset_root + "/activate")
        request("POST", dataset_root + "/eda")
        config = request("GET", root + "/package/configuration")
        config.update(
            document_id=document["id"],
            dataset_id=dataset["id"],
            design="observational",
            observations="independent",
            variables=[
                {
                    "variable_id": vid,
                    "columns": [column],
                    "role": role,
                    "measurement_scale": "ratio",
                }
                for vid, column, role in zip(
                    ids, columns, ["independent", "dependent"], strict=True
                )
            ],
            hypotheses=[
                {
                    "id": str(uuid4()),
                    "source": "general",
                    "kind": "association",
                    "objective": content["general_objective"]["value"],
                    "variable_ids": ids,
                }
            ],
        )
        request("PUT", root + "/package/configuration", json=config)
        package = request("POST", root + "/package/build")
        record = request(
            "POST",
            root + "/analysis/plan",
            json={"package_id": package["id"], "hypothesis_id": package["hypotheses"][0]["id"]},
        )
        plan_root = root + f"/analysis/plans/{record['plan']['id']}"
        request(
            "POST",
            plan_root + "/approve",
            json={"confirm": True, "proposal_token": record["proposal_token"]},
        )
        request("POST", plan_root + "/execute")


def make_demo_app():
    folder = Path(".cache/context-chat-demo")
    settings = ResearchDevSettings(
        _env_file=None,
        cloudflare_account_id="",
        cloudflare_api_token="",
        cloudflare_model="simulado-local-sin-red",
        research_db_path=folder / "demo.sqlite3",
        research_documents_path=folder / "documents",
        research_datasets_path=folder / "datasets",
        cors_origins=["http://127.0.0.1:5176", "http://localhost:5176"],
    )
    app = create_app(settings=settings, conversation_provider=LocalContextProvider())
    seed(app)
    return app


if __name__ == "__main__":
    uvicorn.run(make_demo_app(), host="127.0.0.1", port=8016)
