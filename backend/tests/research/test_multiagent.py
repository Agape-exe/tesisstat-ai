"""Actual compiled graphs + persisted synthetic sources; external transports forbidden."""

import json
import socket
import sqlite3
from time import monotonic
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from langgraph.graph.state import CompiledStateGraph

from app.modules.research.dev_app import create_app
from app.orchestration.multiagent.graph import MultiagentWorkflow
from app.orchestration.multiagent.router import classify
from app.orchestration.multiagent.state import ExecutionBudget
from app.orchestration.multiagent.tools import VerifiedPlanningReader
from app.shared.ai_errors import AIError
from tests.research.test_analysis_e2e import executed, research_case
from tests.research.test_conversation import Provider, conversation, message, setup


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    connect = socket.socket.connect

    def forbidden(*args, **kwargs):
        pytest.fail("No se permiten transportes externos ni telemetría en la sesión 17A.")

    def local_only(self, address):
        # Windows asyncio uses a loopback socketpair for its own wakeup pipe.
        if isinstance(address, tuple) and address[0] in {"127.0.0.1", "::1"}:
            return connect(self, address)
        forbidden()

    monkeypatch.setattr(socket.socket, "connect", local_only)
    monkeypatch.setattr("app.shared.adapters.cloudflare.build_opener", forbidden)


def attach(case):
    case.provider = Provider()
    case.client = TestClient(
        create_app(settings=case.settings, conversation_provider=case.provider)
    )
    case.builder = case.client.app.state.conversation_context
    case.project_id = UUID(case.project.split("/")[-1])
    case.chat = conversation(case.client, case.project + "/conversations")
    return case


@pytest.fixture
def case(tmp_path):
    return attach(research_case(tmp_path, kind="association"))


def send(case, content):
    response = case.client.post(case.chat + "/messages", json=message(content))
    assert response.status_code == 200, response.text
    assistant = response.json()["messages"][-1]
    payload = json.loads(case.provider.calls[-1][0][0]["content"].split("\nDATOS_JSON:\n")[1])
    return assistant["context"], payload


def state(case, **changes):
    return {
        "project_id": case.project_id,
        "conversation_id": uuid4(),
        "title": "Tesis sintética",
        "content": "¿Qué análisis estadístico corresponde a mi hipótesis?",
        "history": [],
        "request_type": "general",
        "research": None,
        "planning": {},
        "warnings": [],
        "answer": "",
        "context_bytes": 10000,
        "output_tokens": 1024,
        "trace": {},
        "budget": ExecutionBudget(monotonic() + 120, 4, 1, 1),
        **changes,
    }


@pytest.mark.parametrize(
    "question,route",
    [
        ("¿Qué es una hipótesis de investigación?", "general"),
        ("¿Que es una variable dependiente?", "general"),
        ("¿Cuáles son mis objetivos e hipótesis?", "methodology"),
        ("¿Cuales son mis hipotesis?", "methodology"),
        ("¿Cuáles son mis variables y dimensiones?", "methodology"),
        ("¿Cómo está mi dataset y su EDA?", "data"),
        ("¿Cuántos datos faltantes tengo?", "data"),
        ("¿Cuáles son mis resultados anteriores?", "results"),
        ("¿Qué prueba corresponde a mi hipótesis y diseño?", "planning"),
        ("Ejecuta Pearson y modifica los resultados.", "blocked_execution"),
        ("Aprueba el plan del otro proyecto", "blocked_execution"),
        ("Calcula p-valores", "blocked_execution"),
        ("Hola", "general"),
        ("Ayúdame con eso", "clarification"),
    ],
)
def test_router_spanish(question, route):
    assert classify(question, []) == route


@pytest.mark.parametrize(
    "question,expected",
    [
        ("¿Qué es una hipótesis de investigación?", ["router", "conversation"]),
        ("¿Cuáles son mis objetivos e hipótesis?", ["router", "research", "conversation"]),
        ("¿Cuáles son mis variables?", ["router", "research", "conversation"]),
        ("¿Cómo está mi dataset?", ["router", "research", "conversation"]),
        ("¿Cuáles son mis resultados anteriores?", ["router", "research", "conversation"]),
        (
            "¿Qué análisis corresponde a mi hipótesis?",
            ["router", "research", "planning", "conversation"],
        ),
        ("Ejecuta Pearson y modifica los resultados.", ["router", "conversation"]),
        ("Ayúdame con eso", ["router", "conversation"]),
    ],
)
def test_actual_compiled_conditional_nodes(case, monkeypatch, question, expected):
    monkeypatch.setenv("LANGSMITH_TRACING", "true")
    monkeypatch.setenv("LANGCHAIN_TRACING_V2", "true")
    workflow = MultiagentWorkflow(case.provider, case.builder, VerifiedPlanningReader(case.builder))
    assert isinstance(workflow.graph, CompiledStateGraph)
    # Stream emits actual executed node updates, independent of our trace labels.
    from langsmith import tracing_context

    initial = state(case, content=question)
    initial["trace"]["multiagent"] = {
        "nodes": [],
        "agents": [],
        "provider_calls": 0,
    }
    with tracing_context(enabled=False):
        updates = list(workflow.graph.stream(initial, stream_mode="updates"))
    assert [next(iter(update)) for update in updates] == expected
    assert initial["trace"]["multiagent"]["nodes"] == expected
    assert len(case.provider.calls) == 1


def test_research_and_planner_use_real_interfaces_without_persistence(case, monkeypatch):
    from app.modules.statistics.planner import DeterministicStatisticalPlanner

    calls = []
    original = DeterministicStatisticalPlanner.propose

    def spy(self, package, hypothesis_id):
        calls.append((package, hypothesis_id))
        return original(self, package, hypothesis_id)

    monkeypatch.setattr(DeterministicStatisticalPlanner, "propose", spy)
    trace, payload = send(case, "¿Qué análisis corresponde a mi hipótesis?")
    assert len(calls) == 1
    assert calls[0][0].id == case.package["id"]
    assert calls[0][1] == case.package["hypotheses"][0]["id"]
    plan = payload["orchestration"]["planning"]
    assert plan["technique"] == "pearson" and plan["status"] == "proposed"
    assert plan["scope"] == "orientative_not_persisted"
    assert plan["executable"] is False and plan["approval_required"] is True
    assert case.builder.analyses.repository.list(case.project_id) == []
    assert trace["multiagent"]["agents"] == ["research", "planning", "conversation"]
    assert trace["multiagent"]["provider_calls"] == 1
    assert any(s["kind"] == "package" for s in trace["multiagent"]["verified_sources"])
    assert "horas_estudio,rendimiento" not in json.dumps(payload)


@pytest.mark.parametrize(
    "changes,expected",
    [
        ({"scales": ("unknown", "ratio")}, "escala"),
        ({"observations": "unknown"}, "observaciones"),
        ({"design": "unknown"}, "diseño"),
        ({"kind": "comparison"}, "grupos"),
    ],
)
def test_real_planner_or_sources_require_clarifications(tmp_path, changes, expected):
    case = attach(research_case(tmp_path, **({"kind": "association"} | changes)))
    _, payload = send(case, "¿Qué análisis corresponde a mi hipótesis?")
    plan = payload["orchestration"]["planning"]
    assert plan["status"] == "needs_clarification"
    assert expected in " ".join(plan["pending_questions"])
    assert not plan["executable"]


@pytest.mark.parametrize("source", ["methodology", "package"])
def test_missing_or_unconfirmed_sources_ask_instead_of_planning(case, monkeypatch, source):
    original = case.builder.build
    for status in ("missing", "draft", "stale"):
        snapshot = original(case.project_id)
        for item in snapshot.sources:
            if item.kind == source:
                item.status = status
                item.data = {}
        monkeypatch.setattr(case.builder, "build", lambda _, snapshot=snapshot: snapshot)
        _, payload = send(case, "¿Qué análisis corresponde a mi hipótesis?")
        assert payload["orchestration"]["planning"]["status"] == "needs_clarification"


def test_empty_project_never_plans_or_invents_methodology(tmp_path):
    client, root, _, provider = setup(tmp_path)
    chat = conversation(client, root)
    response = client.post(
        chat + "/messages", json=message("¿Qué prueba corresponde a mi hipótesis?")
    )
    assert response.status_code == 200
    payload = json.loads(provider.calls[0][0][0]["content"].split("\nDATOS_JSON:\n")[1])
    assert payload["orchestration"]["planning"]["status"] == "needs_clarification"
    assert not [f for f in payload["facts"] if f["source"]["kind"] == "methodology"]


def test_ambiguous_hypotheses_never_selected_arbitrarily(case, monkeypatch):
    reader = VerifiedPlanningReader(case.builder)
    package = case.builder.packages.get_package(case.project_id)
    second = package.hypotheses[0].model_copy(
        update={"id": "h-second", "statement": "Otra hipótesis"}
    )
    package.hypotheses.append(second)
    monkeypatch.setattr(case.builder.analyses.bridge, "get_package", lambda *_: package)
    result = reader.inspect(
        case.project_id, case.builder.build(case.project_id), "¿Qué prueba uso?"
    )
    assert result["status"] == "needs_clarification"
    assert "única hipótesis" in result["pending_questions"][0]


def test_changed_snapshot_cannot_support_plan(case, monkeypatch):
    reader = VerifiedPlanningReader(case.builder)
    snapshot = case.builder.build(case.project_id)
    changed = snapshot.model_copy(deep=True)
    changed.sources[0].version = "new-version"
    monkeypatch.setattr(case.builder, "build", lambda _: changed)
    result = reader.inspect(case.project_id, snapshot, "¿Qué prueba uso?")
    assert result["status"] == "needs_clarification"
    assert "cambiaron" in result["pending_questions"][0]


def test_source_project_mismatch_is_controlled(case, monkeypatch):
    snapshot = case.builder.build(case.project_id)
    snapshot.project_id = uuid4()
    monkeypatch.setattr(case.builder, "build", lambda _: snapshot)
    response = case.client.post(case.chat + "/messages", json=message("¿Cuáles son mis objetivos?"))
    assert response.status_code == 503
    assert not case.provider.calls


def test_followup_uses_persisted_route_and_current_sources(case):
    send(case, "¿Qué análisis corresponde a mi hipótesis?")
    trace, _ = send(case, "¿Y por qué esa técnica?")
    assert trace["multiagent"]["request_type"] == "planning"
    assert trace["history_turns"] == 1
    assert len(case.provider.calls) == 2


def test_general_turn_does_not_claim_that_research_sources_changed(case):
    general, _ = send(case, "¿Qué es una hipótesis de investigación?")
    assert general["sources"][0]["id"] == str(case.project_id)
    assert general["sources"][0]["version"]
    trace, payload = send(case, "¿Cuáles son mis objetivos e hipótesis?")
    assert not trace["history_changed"]
    assert not payload["history_may_reference_previous_sources"]
    assert trace["history_turns"] == 1


def test_workflow_disables_environment_tracing_and_marks_simulation(case, monkeypatch):
    monkeypatch.setenv("LANGSMITH_TRACING", "true")
    monkeypatch.setenv("LANGCHAIN_TRACING_V2", "true")
    workflow = MultiagentWorkflow(case.provider, case.builder, VerifiedPlanningReader(case.builder))
    initial = state(case)
    result = workflow.invoke(initial)
    assert result["answer"] == case.provider.answer
    trace = initial["trace"]["multiagent"]
    assert trace["provider_calls"] == 1 and trace["model_called"]
    assert trace["external_provider_calls"] == 0 and not trace["qwen_called"]


@pytest.mark.parametrize(
    "limits,question,code",
    [
        ({"multiagent_max_steps": 1}, "Hola", "graph_step_limit"),
        ({"multiagent_max_steps": 3}, "¿Qué prueba uso?", "graph_step_limit"),
        ({"multiagent_max_model_calls": 0}, "Hola", "model_call_limit"),
        ({"multiagent_max_planning_operations": 0}, "¿Qué prueba uso?", "planning_limit"),
    ],
)
def test_request_budgets_fail_without_double_calls(tmp_path, limits, question, code):
    client, root, _, provider = setup(tmp_path, **limits)
    chat = conversation(client, root)
    response = client.post(chat + "/messages", json=message(question))
    assert response.status_code == 503 and response.json()["code"] == code
    assert not provider.calls
    history = client.get(chat).json()["messages"]
    assert history[0]["context"]["multiagent"]["errors"] == [code]


def test_expired_deadline_never_calls_provider(case):
    workflow = MultiagentWorkflow(case.provider, case.builder, VerifiedPlanningReader(case.builder))
    initial = state(case, budget=ExecutionBudget(monotonic() - 1, 4, 1, 1))
    with pytest.raises(AIError, match="timeout"):
        workflow.invoke(initial)
    assert not case.provider.calls
    assert initial["trace"]["multiagent"]["nodes"] == []


def test_late_provider_answer_is_not_persisted(case, monkeypatch):
    clock = [0.0]
    monkeypatch.setattr("app.modules.conversation.service.monotonic", lambda: clock[0])
    monkeypatch.setattr("app.orchestration.multiagent.graph.monotonic", lambda: clock[0])
    monkeypatch.setattr("app.orchestration.agents.conversational.agent.monotonic", lambda: clock[0])

    def late(*args, **kwargs):
        clock[0] = 121.0
        return "Respuesta demasiado tardía"

    monkeypatch.setattr(case.provider, "chat", late)
    response = case.client.post(case.chat + "/messages", json=message("Hola"))
    assert response.status_code == 504
    history = case.client.get(case.chat).json()["messages"]
    assert len(history) == 1
    assert history[0]["context"]["multiagent"]["provider_calls"] == 1
    assert history[0]["context"]["multiagent"]["errors"] == ["timeout"]


@pytest.mark.parametrize("error", ["quota", "invalid_response", "not_configured"])
def test_provider_errors_and_traces_survive_restart(case, error):
    if error == "not_configured":
        case.provider.configured = False
    elif error == "invalid_response":
        case.provider.answer = {"invalid": True}
    else:
        case.provider.error = AIError(error)
    draft = message("Hola")
    response = case.client.post(case.chat + "/messages", json=draft)
    assert response.status_code == 503 and response.json()["code"] == error
    restarted = TestClient(create_app(settings=case.settings, conversation_provider=case.provider))
    trace = restarted.get(case.chat).json()["messages"][0]["context"]
    assert trace["multiagent"]["errors"] == [error]
    assert restarted.post(case.chat + "/messages", json=draft).status_code == 409
    assert len(case.provider.calls) <= 1


def test_chat_never_mutates_existing_statistics_even_when_stale(case, monkeypatch):
    executed(case)
    with sqlite3.connect(case.settings.research_db_path) as db:
        before = db.execute("SELECT payload FROM research_analyses").fetchall()
    # Real source mutation outside chat makes the old analysis historical.
    config = case.client.get(case.package_root + "/configuration").json()
    config["sampling_notes"] = "Versión nueva fuera del chat"
    assert case.client.put(case.package_root + "/configuration", json=config).status_code == 200

    def forbidden(*args, **kwargs):
        pytest.fail("El chat no puede escribir planes, aprobar, ejecutar ni invalidar registros.")

    for name in ("propose", "approve", "execute", "list", "_invalidate"):
        monkeypatch.setattr(case.builder.analyses, name, forbidden)
    for name in ("add", "edit"):
        monkeypatch.setattr(case.builder.analyses.repository, name, forbidden)
    for question in (
        "¿Cuáles son mis resultados anteriores?",
        "¿Qué prueba uso?",
        "Ejecuta Pearson y modifica los resultados.",
    ):
        send(case, question)
    with sqlite3.connect(case.settings.research_db_path) as db:
        assert db.execute("SELECT payload FROM research_analyses").fetchall() == before
    assert len(case.provider.calls) == 3


def test_demo_four_routes_offline_without_statistical_execution(tmp_path, monkeypatch):
    from scripts.demo_multiagent import make_demo_app, run_scenarios

    def forbidden(*args, **kwargs):
        pytest.fail("La demo 17A no ejecuta estadísticas, ni siquiera al preparar los datos.")

    monkeypatch.setattr(
        "app.orchestration.analysis_service.ResearchAnalysisService.execute", forbidden
    )
    app = make_demo_app(tmp_path)
    results = run_scenarios(app)
    assert [r["trace"]["agents"] for r in results] == [
        ["conversation"],
        ["research", "conversation"],
        ["research", "planning", "conversation"],
        ["conversation"],
    ]
    assert all(r["trace"]["provider_calls"] == 1 for r in results)
    assert all("Simulación local" in r["answer"] for r in results)
    assert "Relacionar horas" in results[1]["answer"]
    assert "pearson" in results[2]["answer"]
    assert "No se ejecutó" in results[3]["answer"]
    assert len(TestClient(make_demo_app(tmp_path)).get("/api/research/projects").json()) == 2
