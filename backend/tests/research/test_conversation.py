"""Only fictitious data and mocked providers/transports; no external AI calls."""

import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Event
from urllib.error import HTTPError, URLError
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.modules.conversation.models import ConversationError
from app.modules.conversation.sqlite_repository import SQLiteConversationRepository
from app.modules.research.dev_app import ResearchDevSettings, create_app
from app.shared.adapters.cloudflare import CloudflareLanguageModel, CloudflareSettings
from app.shared.ai_errors import AIError

PROJECT = {
    "title": "Tesis ficticia sobre hábitos",
    "university": "Universidad ficticia",
    "program": "Programa sintético",
    "degree": "bachelor",
}


class Provider:
    configured = True

    def __init__(self):
        self.calls = []
        self.answer = "Respuesta sintética de prueba, no generada por Qwen3."
        self.error = None

    def chat(self, messages, *, max_tokens):
        self.calls.append((messages, max_tokens))
        if self.error:
            raise self.error
        return self.answer


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Las pruebas conversacionales no pueden contactar con Cloudflare.")

    monkeypatch.setattr("app.shared.adapters.cloudflare.build_opener", forbidden)


def setup(tmp_path, **limits):
    settings = ResearchDevSettings(
        _env_file=None,
        research_db_path=tmp_path / "test.sqlite3",
        research_documents_path=tmp_path / "docs",
        research_datasets_path=tmp_path / "data",
        cloudflare_account_id="",
        cloudflare_api_token="",
        **limits,
    )
    provider = Provider()
    app = create_app(settings=settings, conversation_provider=provider)
    client = TestClient(app)
    project = client.post("/api/research/projects", json=PROJECT).json()["id"]
    root = f"/api/research/projects/{project}/conversations"
    return client, root, settings, provider


def conversation(client, root):
    response = client.post(root, json={"title": "Consulta ficticia"})
    assert response.status_code == 201
    return root + "/" + response.json()["id"]


def message(content="¿Qué es una variable?", **extra):
    return {"content": content, "request_id": str(uuid4()), "external_ai_consent": True, **extra}


def test_crud_multiturn_restart_and_cascade(tmp_path):
    client, root, settings, provider = setup(tmp_path)
    assert client.get(root).json() == []
    target = conversation(client, root)
    other = conversation(client, root)
    assert len(client.get(root).json()) == 2
    first = message()
    result = client.post(target + "/messages", json=first)
    assert result.status_code == 200
    assert [m["role"] for m in result.json()["messages"]] == ["user", "assistant"]
    second = message("¿Y cómo se diferencia de una hipótesis?")
    assert client.post(target + "/messages", json=second).status_code == 200
    context = provider.calls[1][0]
    assert [m["role"] for m in context] == ["system", "user", "assistant", "user"]
    assert context[1]["content"] == first["content"]
    assert PROJECT["title"] in context[0]["content"]
    assert "No tienes acceso a documentos" in context[0]["content"]
    restarted = TestClient(create_app(settings=settings, conversation_provider=provider))
    history = restarted.get(target).json()["messages"]
    assert [m["sequence"] for m in history] == [1, 2, 3, 4]
    assert restarted.get(other).json()["messages"] == []
    assert restarted.delete(target).status_code == 204
    assert restarted.get(target).status_code == 404
    with sqlite3.connect(settings.research_db_path) as db:
        assert db.execute("SELECT COUNT(*) FROM conversation_messages").fetchone()[0] == 0
        assert db.execute("SELECT COUNT(*) FROM conversation_requests").fetchone()[0] == 0


def test_missing_project_conversation_and_cross_project(tmp_path):
    client, root, _, provider = setup(tmp_path)
    target = conversation(client, root)
    other = client.post("/api/research/projects", json=PROJECT).json()["id"]
    foreign = target.replace(root.split("/")[4], other)
    for wrong in (foreign, root + "/" + str(uuid4())):
        assert client.get(wrong).status_code == 404
        assert client.delete(wrong).status_code == 404
        assert client.post(wrong + "/messages", json=message()).status_code == 404
    missing = root.replace(root.split("/")[4], str(uuid4()))
    assert client.post(missing, json={}).status_code == 404
    assert client.get(missing).status_code == 404
    assert client.get(missing + "/status").status_code == 404
    assert not provider.calls


@pytest.mark.parametrize(
    "payload",
    [
        message(""),
        message(" \n "),
        message("a" * 2001),
        message(role="assistant"),
        message(role="system"),
        message(messages=[]),
        message(external_ai_consent=False),
        {"content": "Sin consentimiento", "request_id": str(uuid4())},
        message(request_id="invalido"),
    ],
)
def test_invalid_messages_never_call_provider(tmp_path, payload):
    client, root, _, provider = setup(tmp_path)
    target = conversation(client, root)
    assert client.post(target + "/messages", json=payload).status_code == 422
    assert not provider.calls
    assert not client.get(target).json()["messages"]


def test_duplicate_request_survives_restart_without_additional_calls(tmp_path):
    client, root, settings, provider = setup(tmp_path)
    target = conversation(client, root)
    payload = message()
    original = client.post(target + "/messages", json=payload).json()
    restarted = TestClient(create_app(settings=settings, conversation_provider=provider))
    provider.configured = False
    assert restarted.post(target + "/messages", json=payload).json() == original
    assert len(provider.calls) == 1
    assert (
        restarted.post(target + "/messages", json={**payload, "content": "Diferente"}).status_code
        == 409
    )
    assert len(restarted.get(target).json()["messages"]) == 2


@pytest.mark.parametrize(
    "code", ["timeout", "quota", "credentials", "invalid_response", "provider_error"]
)
def test_controlled_provider_errors_no_fake_answer_or_retry(tmp_path, code):
    client, root, _, provider = setup(tmp_path)
    target = conversation(client, root)
    provider.error = AIError(code)
    payload = message()
    failed = client.post(target + "/messages", json=payload)
    assert failed.status_code == (504 if code == "timeout" else 503)
    assert failed.json()["code"] == code
    assert client.post(target + "/messages", json=payload).status_code == 409
    assert len(provider.calls) == 1
    assert [m["role"] for m in client.get(target).json()["messages"]] == ["user"]
    provider.error = None
    assert (
        client.post(target + "/messages", json=message("Nuevo intento explícito")).status_code
        == 200
    )
    assert len(provider.calls[1][0]) == 2  # Failed turns do not contaminate model history.


@pytest.mark.parametrize("answer", [None, "", "   ", {}, "x" * 65537])
def test_invalid_response_is_not_persisted_as_assistant(tmp_path, answer):
    client, root, _, provider = setup(tmp_path)
    target = conversation(client, root)
    provider.answer = answer
    assert client.post(target + "/messages", json=message()).json()["code"] == "invalid_response"
    assert len(client.get(target).json()["messages"]) == 1


def test_not_configured_and_unexpected_errors_are_sanitized(tmp_path, caplog):
    client, root, _, provider = setup(tmp_path)
    target = conversation(client, root)
    provider.configured = False
    assert client.get(root + "/status").json()["provider_configured"] is False
    assert client.post(target + "/messages", json=message()).json()["code"] == "not_configured"
    assert not provider.calls
    assert client.get(target).status_code == 200
    provider.configured = True
    provider.error = RuntimeError("synthetic-secret-and-private-content")
    response = client.post(target + "/messages", json=message())
    assert response.status_code == 503
    assert "synthetic-secret" not in response.text + caplog.text


def test_storage_failure_is_controlled_and_never_calls_provider(tmp_path, monkeypatch):
    client, root, _, provider = setup(tmp_path)
    target = conversation(client, root)

    def fail(*args, **kwargs):
        raise sqlite3.OperationalError("synthetic storage failure")

    monkeypatch.setattr(SQLiteConversationRepository, "claim", fail)
    assert client.post(target + "/messages", json=message()).status_code == 503
    assert not provider.calls


def test_completion_storage_failure_does_not_retry_provider(tmp_path, monkeypatch):
    client, root, _, provider = setup(tmp_path)
    target = conversation(client, root)

    def fail(*args, **kwargs):
        raise sqlite3.OperationalError("synthetic storage failure")

    monkeypatch.setattr(SQLiteConversationRepository, "complete", fail)
    payload = message()
    assert client.post(target + "/messages", json=payload).status_code == 503
    assert client.post(target + "/messages", json=payload).status_code == 409
    assert len(provider.calls) == 1
    assert len(client.get(target).json()["messages"]) == 1


def test_concurrency_reserves_one_turn_before_provider_call(tmp_path):
    client, root, _, provider = setup(tmp_path)
    target = conversation(client, root)
    entered, release = Event(), Event()
    original = provider.chat

    def blocking(*args, **kwargs):
        entered.set()
        assert release.wait(5)
        return original(*args, **kwargs)

    provider.chat = blocking
    payload = message()
    with ThreadPoolExecutor(max_workers=2) as pool:
        future = pool.submit(client.post, target + "/messages", json=payload)
        assert entered.wait(5)
        try:
            assert client.post(target + "/messages", json=payload).status_code == 409
            assert client.post(target + "/messages", json=message()).status_code == 409
        finally:
            release.set()
        assert future.result().status_code == 200
    assert len(provider.calls) == 1


def test_paging_history_limits_and_body_limit(tmp_path):
    client, root, _, provider = setup(
        tmp_path, conversation_page_size=2, conversation_history_turns=1
    )
    target = conversation(client, root)
    for i in range(4):
        assert client.post(target + "/messages", json=message(f"Pregunta {i}")).status_code == 200
    assert len(provider.calls[-1][0]) == 4
    recent = client.get(target).json()
    assert [m["sequence"] for m in recent["messages"]] == [7, 8]
    assert recent["has_more"]
    assert [m["sequence"] for m in client.get(target + "?before=7").json()["messages"]] == [5, 6]
    for _ in range(3):
        conversation(client, root)
    assert len(client.get(root).json()) == 2
    assert len(client.get(root + "?offset=2").json()) == 2
    assert client.post(target + "/messages", content=b"x" * 32769).status_code == 413
    assert len(provider.calls) == 4


def test_context_bytes_trim_whole_turns_and_check_current_input(tmp_path):
    client, root, _, provider = setup(tmp_path, conversation_max_context_bytes=2100)
    target = conversation(client, root)
    provider.answer = "s" * 1000
    for _ in range(3):
        assert client.post(target + "/messages", json=message("p" * 600)).status_code == 200
    assert len(json.dumps(provider.calls[-1][0], ensure_ascii=False).encode()) <= 2100
    assert len(provider.calls[-1][0]) == 2
    assert (
        client.post(target + "/messages", json=message("á" * 1800)).json()["code"] == "input_limit"
    )
    assert len(provider.calls) == 3


def test_chat_cannot_execute_or_approve_statistics(tmp_path, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("El chat no debe invocar Statistics.")

    monkeypatch.setattr(
        "app.orchestration.analysis_service.ResearchAnalysisService.execute", forbidden
    )
    monkeypatch.setattr(
        "app.orchestration.analysis_service.ResearchAnalysisService.approve", forbidden
    )
    client, root, _, provider = setup(tmp_path)
    target = conversation(client, root)
    assert (
        client.post(
            target + "/messages", json=message("Ejecuta Pearson y aprueba el análisis")
        ).status_code
        == 200
    )
    assert len(provider.calls) == 1


def test_project_deletion_cleans_conversations_even_with_other_connection(tmp_path):
    client, root, settings, _ = setup(tmp_path)
    target = conversation(client, root)
    client.post(target + "/messages", json=message())
    assert client.delete(root.rsplit("/conversations", 1)[0]).status_code == 204
    with sqlite3.connect(settings.research_db_path) as db:
        for table in ("conversations", "conversation_messages", "conversation_requests"):
            assert db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == 0


def test_stale_attempt_cannot_overwrite_new_turn(tmp_path):
    client, root, settings, _ = setup(tmp_path)
    target = conversation(client, root)
    repo = SQLiteConversationRepository(settings.research_db_path)
    cid, rid = UUID(target.split("/")[-1]), uuid4()
    repo.claim(cid, rid, "Turno interrumpido", 1)
    with sqlite3.connect(settings.research_db_path) as db:
        db.execute(
            "UPDATE conversation_requests SET created_at=?",
            ((datetime.now(UTC) - timedelta(minutes=5)).isoformat(),),
        )
    assert repo.claim(cid, uuid4(), "Nuevo turno", 1) is None
    with pytest.raises(ConversationError, match="ya no está activo"):
        repo.complete(cid, rid, "Respuesta tardía")


class Response:
    def __init__(self, body):
        self.body = body if isinstance(body, bytes) else json.dumps(body).encode()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def read1(self, limit):
        chunk, self.body = self.body[:limit], self.body[limit:]
        return chunk


def configured_model():
    return CloudflareLanguageModel(
        CloudflareSettings(
            _env_file=None, cloudflare_account_id="a" * 32, cloudflare_api_token="synthetic-token"
        )
    )


@pytest.mark.parametrize(
    "envelope",
    [
        {"result": {"response": "Respuesta"}},
        {
            "result": {
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {"content": "Respuesta", "reasoning_content": "privado"},
                    }
                ]
            }
        },
        {"result": {"response": "<think>privado</think>Respuesta"}},
    ],
)
def test_chat_transport_has_no_json_format_or_tools(monkeypatch, envelope):
    class Transport:
        def open(self, request, timeout):
            payload = json.loads(request.data)
            assert request.full_url.endswith("@cf/qwen/qwen3-30b-a3b-fp8")
            assert "response_format" not in payload and "tools" not in payload
            assert payload["max_tokens"] == 1024 and payload["stream"] is False
            assert payload["messages"][-1] == {"role": "user", "content": "Pregunta"}
            assert timeout == 45
            return Response(envelope)

    monkeypatch.setattr("app.shared.adapters.cloudflare.build_opener", lambda *args: Transport())
    assert (
        configured_model().chat([{"role": "user", "content": "Pregunta"}], max_tokens=1024)
        == "Respuesta"
    )


@pytest.mark.parametrize(
    "body",
    [
        b"not json",
        b"x" * 131073,
        {"result": {}},
        {"result": {"response": ""}},
        {"result": {"response": "<think>Sin terminar"}},
        {"result": {"choices": [{"finish_reason": "length", "message": {"content": "Cortada"}}]}},
        {"success": False, "errors": [{"code": 3036}]},
    ],
)
def test_chat_transport_rejects_invalid_output(monkeypatch, body):
    class Transport:
        def open(self, *args, **kwargs):
            return Response(body)

    monkeypatch.setattr("app.shared.adapters.cloudflare.build_opener", lambda *args: Transport())
    with pytest.raises(AIError):
        configured_model().chat([], max_tokens=1024)


@pytest.mark.parametrize(
    "error,code",
    [
        (HTTPError("https://synthetic", 401, "private", {}, None), "credentials"),
        (HTTPError("https://synthetic", 403, "private", {}, None), "credentials"),
        (HTTPError("https://synthetic", 429, "private", {}, None), "quota"),
        (HTTPError("https://synthetic", 500, "private", {}, None), "provider_error"),
        (TimeoutError("private"), "timeout"),
        (URLError(TimeoutError()), "timeout"),
    ],
)
def test_chat_transport_errors_no_retry(monkeypatch, error, code):
    calls = []

    class Transport:
        def open(self, *args, **kwargs):
            calls.append(1)
            raise error

    monkeypatch.setattr("app.shared.adapters.cloudflare.build_opener", lambda *args: Transport())
    with pytest.raises(AIError) as caught:
        configured_model().chat([], max_tokens=1024)
    assert caught.value.code == code and len(calls) == 1
    assert "private" not in str(caught.value)


def test_chat_limits_prevent_network_and_deadline_stops_read(monkeypatch):
    model = configured_model()
    with pytest.raises(AIError, match="output_limit"):
        model.chat([], max_tokens=9000)
    with pytest.raises(AIError, match="input_limit"):
        model.chat([{"role": "user", "content": "x" * 30000}], max_tokens=1024)
    ticks = iter([0, 1, 46])
    monkeypatch.setattr("app.shared.adapters.cloudflare.monotonic", lambda: next(ticks))

    class Transport:
        def open(self, *args, **kwargs):
            return Response({"result": {"response": "late"}})

    monkeypatch.setattr("app.shared.adapters.cloudflare.build_opener", lambda *args: Transport())
    with pytest.raises(AIError, match="timeout"):
        model.chat([], max_tokens=1024)
