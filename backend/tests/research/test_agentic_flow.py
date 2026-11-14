from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock

import pytest

from app.core.config import Settings
from app.modules.conversation.agentic_service import AgenticChatService


@pytest.fixture
def agentic_service():
    with TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "projects.sqlite3"
        settings = Settings()
        sources_mock = MagicMock()
        tutor_mock = MagicMock()
        reports_mock = MagicMock()
        service = AgenticChatService(
            db_path=db_path,
            settings=settings,
            sources=sources_mock,
            tutor=tutor_mock,
            reports=reports_mock,
        )
        yield service


def test_initial_conversation_has_no_upload_requested(agentic_service):
    conv = agentic_service.get_or_create_conversation("proj-1")
    assert conv.id is not None
    assert len(conv.messages) == 1
    assert "upload_requested" not in conv.messages[0].meta
    assert len(conv.messages[0].meta.get("quick_replies", [])) == 3


def test_user_answers_direct_data_requests_dataset_only(agentic_service):
    conv = agentic_service.get_or_create_conversation("proj-1")
    updated = agentic_service.send_message(
        "proj-1",
        conv.id,
        "Tengo datos directos (calificaciones, notas de pretest/posttest o mediciones).",
    )
    assert len(updated.messages) == 3  # greeting, user, assistant
    last_msg = updated.messages[-1]
    assert last_msg.role == "assistant"
    assert "upload_requested" in last_msg.meta
    assert last_msg.meta["upload_requested"]["mode"] == "dataset_only"
    assert "adjunta tu archivo de datos" in last_msg.content.lower()


def test_user_answers_instrument_requests_instrument_and_dataset(agentic_service):
    conv = agentic_service.get_or_create_conversation("proj-1")
    updated = agentic_service.send_message(
        "proj-1",
        conv.id,
        "Tengo un instrumento de recolección (encuesta, cuestionario o test).",
    )
    assert len(updated.messages) == 3
    last_msg = updated.messages[-1]
    assert last_msg.role == "assistant"
    assert "upload_requested" in last_msg.meta
    assert last_msg.meta["upload_requested"]["mode"] == "instrument_and_dataset"
    assert "instrumento de investigación" in last_msg.content.lower()


def test_user_asks_for_difference_explains_without_upload(agentic_service):
    conv = agentic_service.get_or_create_conversation("proj-1")
    updated = agentic_service.send_message(
        "proj-1",
        conv.id,
        "No estoy seguro, por favor explícame la diferencia entre tener un instrumento o datos directos.",
    )
    assert len(updated.messages) == 3
    last_msg = updated.messages[-1]
    assert last_msg.role == "assistant"
    assert "upload_requested" not in last_msg.meta
    assert "diferencia" in last_msg.content.lower()
    assert len(last_msg.meta.get("quick_replies", [])) == 2


def test_send_message_with_conv_init_resolves_cleanly(agentic_service):
    # If client passed 'conv-init' fallback ID
    updated = agentic_service.send_message(
        "proj-1",
        "conv-init",
        "Tengo datos directos (ej. notas)",
    )
    assert updated.id != "conv-init"
    assert len(updated.messages) >= 2
