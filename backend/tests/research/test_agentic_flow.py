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


def test_t_paired_calculates_correct_standard_error_and_not_0_528():
    from app.modules.statistics.comparisons import t_paired
    # 23 pairs from Notas.xlsx 2°A Experimental (Promedio Pretest vs Promedio Posttest)
    pre = [16.666666666666668, 17.666666666666668, 18.333333333333332, 18.0, 17.333333333333332,
           17.333333333333332, 17.0, 17.0, 16.333333333333332, 16.666666666666668,
           17.666666666666668, 17.666666666666668, 15.333333333333334, 17.333333333333332,
           17.666666666666668, 17.0, 15.666666666666666, 16.333333333333332, 18.0, 17.0,
           17.0, 17.666666666666668, 16.666666666666668]
    post = [17.333333333333332, 18.0, 18.666666666666668, 18.333333333333332, 18.666666666666668,
            18.0, 17.666666666666668, 18.0, 18.333333333333332, 18.0, 17.333333333333332,
            17.333333333333332, 17.333333333333332, 18.333333333333332, 17.666666666666668,
            18.0, 17.666666666666668, 17.0, 18.0, 18.333333333333332, 18.333333333333332,
            18.0, 18.0]

    # Posttest - Pretest
    res = t_paired(post, pre)
    metrics = res.metrics

    # Standard error must be SD(diff) / sqrt(n) = 0.1449933974...
    assert "standard_error" in metrics
    assert metrics["standard_error"] == pytest.approx(0.1449933974, abs=1e-5)
    assert metrics["standard_error"] != pytest.approx(0.528, abs=1e-2)
    assert metrics["mean_difference"] == pytest.approx(0.8260869565, abs=1e-4)
    assert metrics["t_statistic"] == pytest.approx(5.6974108561, abs=1e-4)
    assert metrics["degrees_of_freedom"] == 22.0
    assert metrics["p_value"] < 0.001


def test_execute_analysis_regression_and_proposal_executed_flag(agentic_service, monkeypatch):
    # Setup conversation with a proposal message
    conv = agentic_service.get_or_create_conversation("proj-audit")
    agentic_service._add_message(
        conv.id,
        "assistant",
        "He preparado una propuesta estadística para contrastar tus datos.",
        meta={"proposal": {"technique": "paired", "justification": "Comparación pre/post", "variables": ["Pre", "Post"]}},
    )

    # Mock execute_chat_analysis return value
    mock_res = {
        "analysis_id": "an-123",
        "technique": "t_paired",
        "metrics": {
            "n": 23,
            "mean_difference": 0.8260869565,
            "t_statistic": 5.6974108561,
            "degrees_of_freedom": 22,
            "p_value": 0.00000991637,
            "cohens_dz": 1.1879922863,
            "standard_error": 0.1449933974,
            "mean_difference_ci_95_low": 0.5253890546,
            "mean_difference_ci_95_high": 1.1267848585,
        },
        "presentation": {},
        "variable_summaries": {},
        "figures": [],
    }
    monkeypatch.setattr(
        "app.modules.conversation.agentic_service.execute_chat_analysis",
        lambda tutor, reports, pid, req: mock_res,
    )

    # Execute proposal
    updated = agentic_service.execute_analysis("proj-audit", conv.id, "paired")

    # 1. Existing proposal message must be marked proposal_executed = True
    proposal_msgs = [m for m in updated.messages if "proposal" in m.meta]
    assert len(proposal_msgs) == 1
    assert proposal_msgs[0].meta.get("proposal_executed") is True

    # 2. Execution result message must have accurate, non-0.528 standard error
    exec_msg = updated.messages[-1]
    assert exec_msg.role == "assistant"
    er = exec_msg.meta.get("execution_result")
    assert er is not None
    assert er["standard_error"] == pytest.approx(0.145, abs=1e-3)
    assert er["standard_error"] != 0.528
    assert er["t_stat"] == pytest.approx(5.6974, abs=1e-3)
    assert er["cohen_d"] == pytest.approx(1.188, abs=1e-3)
    assert er["df"] == 22
    assert er["shapiro_wilk"]["assumption_met"] is True
    assert er["shapiro_wilk"]["statistic"] == 0.9475

    # 3. Quick question chips must be student questions, NOT "¿Deseas realizar otro análisis adicional?"
    qqs = exec_msg.meta.get("quick_questions", [])
    assert "¿Deseas realizar otro análisis adicional?" not in qqs
    assert any("Comparar la ganancia" in q for q in qqs)
    assert any("APA 7.ª" in q for q in qqs)

