"""Reproducible four-route demo: synthetic sources, no network or statistical execution."""

import argparse
import json
from pathlib import Path
from uuid import uuid4

import uvicorn
from fastapi.testclient import TestClient

from app.modules.research.dev_app import ResearchDevSettings, create_app
from scripts.demo_context_chat import LocalContextProvider, seed

QUESTIONS = (
    "¿Qué es una hipótesis de investigación?",
    "¿Cuáles son mis objetivos e hipótesis?",
    "¿Qué análisis estadístico corresponde a mi hipótesis?",
    "Ejecuta Pearson y modifica los resultados.",
)


class DemoProvider(LocalContextProvider):
    def chat(self, messages, *, max_tokens):
        payload = json.loads(messages[0]["content"].split("\nDATOS_JSON:\n")[1])
        guidance = payload.get("orchestration", {})
        prefix = "**Simulación local: sin Qwen3 ni conexión externa.**\n\n"
        if guidance.get("request_type") == "general":
            return (
                prefix + "Una hipótesis plantea una afirmación contrastable sobre la investigación."
            )
        if guidance.get("request_type") == "blocked_execution":
            return prefix + (
                "No se ejecutó ningún análisis ni se modificaron resultados. "
                "Utiliza planificación, revisión, aprobación humana y ejecución fuera del chat."
            )
        if guidance.get("planning"):
            plan = guidance["planning"]
            lines = [prefix, "Propuesta orientativa, sin aprobación ni ejecución."]
            if plan.get("technique"):
                lines.append(f"Técnica orientativa: **{plan['technique']}**.")
            if plan.get("rationale"):
                lines.append(plan["rationale"])
            for question in plan.get("pending_questions", []):
                lines.append(f"- Aclaración pendiente: {question}")
            for assumption in plan.get("assumptions_to_check", []):
                lines.append(f"- Condición que debe revisarse: {assumption}")
            lines.append("Revisa y aprueba el plan en el flujo de análisis antes de ejecutarlo.")
            return "\n\n".join(lines)
        return super().chat(messages, max_tokens=max_tokens)


def make_demo_app(folder: Path | None = None):
    folder = folder or Path(".cache/multiagent-demo")
    settings = ResearchDevSettings(
        _env_file=None,
        cloudflare_account_id="",
        cloudflare_api_token="",
        cloudflare_model="simulado-local-sin-red",
        research_db_path=folder / "demo.sqlite3",
        research_documents_path=folder / "documents",
        research_datasets_path=folder / "datasets",
        cors_origins=["http://127.0.0.1:5177", "http://localhost:5177"],
    )
    app = create_app(settings=settings, conversation_provider=DemoProvider())
    seed(app, include_analysis=False)
    return app


def run_scenarios(app):
    client = TestClient(app)
    project = next(
        p for p in client.get("/api/research/projects").json() if "sintética 1" in p["title"]
    )
    root = f"/api/research/projects/{project['id']}/conversations"
    conversation = client.post(root, json={"title": "Demostración LangGraph 17A"}).json()
    output = []
    for question in QUESTIONS:
        response = client.post(
            root + f"/{conversation['id']}/messages",
            json={
                "content": question,
                "request_id": str(uuid4()),
                "external_ai_consent": True,
                "consent_scope": "research_context_v2",
            },
        )
        response.raise_for_status()
        assistant = response.json()["messages"][-1]
        output.append(
            {
                "question": question,
                "answer": assistant["content"],
                "trace": assistant["context"]["multiagent"],
            }
        )
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--serve", action="store_true")
    args = parser.parse_args()
    app = make_demo_app()
    if args.serve:
        uvicorn.run(app, host="127.0.0.1", port=8017)
    else:
        print(json.dumps(run_scenarios(app), ensure_ascii=False, indent=2))
