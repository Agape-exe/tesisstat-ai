from pathlib import Path
from uuid import UUID

import pytest
from pydantic import ValidationError

import app.orchestration.instrument_scoring_preview as scoring_preview_module
from app.orchestration.instrument_scoring_confirmation import (
    InstrumentScoringConfirmationValidator,
    ScoringConfirmationValidationRequest,
    StaleScoringPreviewError,
)
from app.orchestration.instrument_scoring_preview import (
    InstrumentScoringPreviewService,
    ScoringPreviewRequest,
)
from app.orchestration.research_statistics import AuthorizedInstrumentData
from app.shared.instrument_contracts import InstrumentContext

ROOT = Path(__file__).resolve().parents[2]
CONTEXT = InstrumentContext.model_validate_json(
    (ROOT / "docs" / "contracts" / "examples" / "instrument_confirmed_with_mapping.json").read_text(
        encoding="utf-8"
    )
)
RULE_ID = CONTEXT.scoring_rules[0].scoring_rule_id


class FakeInstrumentBridge:
    def __init__(self) -> None:
        self.calls: list[tuple[UUID, UUID, UUID]] = []

    def get_authorized_instrument_data(
        self, project_id: UUID, instrument_id: UUID, scoring_rule_id: UUID
    ) -> AuthorizedInstrumentData:
        self.calls.append((project_id, instrument_id, scoring_rule_id))
        rows = tuple(
            {
                "p1_comunicacion_directa": str(value),
                "p2_info_contradictoria": str(6 - value),
            }
            for value in range(1, 6)
        )
        return AuthorizedInstrumentData(
            context=CONTEXT,
            rows=rows,
            column_names=("p1_comunicacion_directa", "p2_info_contradictoria"),
        )


def preview_request() -> ScoringPreviewRequest:
    return ScoringPreviewRequest(
        project_id=CONTEXT.project_id,
        instrument_id=CONTEXT.instrument_id,
        scoring_rule_id=RULE_ID,
    )


def confirmation_request(fingerprint: str) -> ScoringConfirmationValidationRequest:
    return ScoringConfirmationValidationRequest(
        project_id=CONTEXT.project_id,
        instrument_id=CONTEXT.instrument_id,
        scoring_rule_id=RULE_ID,
        preview_fingerprint=fingerprint,
        confirm=True,
    )


def test_recomputes_and_validates_unchanged_preview() -> None:
    bridge = FakeInstrumentBridge()
    preview_service = InstrumentScoringPreviewService(bridge)  # type: ignore[arg-type]
    accepted = preview_service.preview(preview_request())

    validation = InstrumentScoringConfirmationValidator(preview_service).validate(
        confirmation_request(accepted.fingerprint)
    )

    assert validation.status == "validated"
    assert validation.preview == accepted
    assert len(bridge.calls) == 2


def test_rejects_stale_preview_without_returning_partial_confirmation() -> None:
    preview_service = InstrumentScoringPreviewService(FakeInstrumentBridge())  # type: ignore[arg-type]

    with pytest.raises(StaleScoringPreviewError, match="previsualización cambió"):
        InstrumentScoringConfirmationValidator(preview_service).validate(
            confirmation_request("0" * 64)
        )


def test_engine_version_change_invalidates_accepted_preview(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    preview_service = InstrumentScoringPreviewService(FakeInstrumentBridge())  # type: ignore[arg-type]
    accepted = preview_service.preview(preview_request())
    monkeypatch.setattr(scoring_preview_module, "SCORING_ENGINE_VERSION", "1.0.1")

    with pytest.raises(StaleScoringPreviewError):
        InstrumentScoringConfirmationValidator(preview_service).validate(
            confirmation_request(accepted.fingerprint)
        )


def test_request_requires_literal_confirmation_and_rejects_identity_spoofing() -> None:
    payload = confirmation_request("0" * 64).model_dump()

    with pytest.raises(ValidationError):
        ScoringConfirmationValidationRequest.model_validate({**payload, "confirm": False})
    with pytest.raises(ValidationError):
        ScoringConfirmationValidationRequest.model_validate(
            {**payload, "confirmer_ref": "cliente-suplanta-identidad"}
        )
