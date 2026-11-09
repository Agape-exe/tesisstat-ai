"""Revalidate a scoring preview before Research-owned persistence exists."""

from __future__ import annotations

from secrets import compare_digest
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.orchestration.instrument_scoring_preview import (
    InstrumentScoringPreviewService,
    ScoringPreview,
    ScoringPreviewRequest,
)


class InternalConfirmationModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)


class ScoringConfirmationValidationRequest(InternalConfirmationModel):
    project_id: UUID
    instrument_id: UUID
    scoring_rule_id: UUID
    preview_fingerprint: str = Field(pattern=r"^[a-f0-9]{64}$")
    confirm: Literal[True]


class ScoringConfirmationValidation(InternalConfirmationModel):
    status: Literal["validated"] = "validated"
    preview: ScoringPreview


class StaleScoringPreviewError(ValueError):
    """Raised when the accepted preview no longer matches current sources or logic."""


class InstrumentScoringConfirmationValidator:
    """Recompute and compare previews without confirming or persisting them."""

    def __init__(self, preview_service: InstrumentScoringPreviewService) -> None:
        self.preview_service = preview_service

    def validate(
        self, request: ScoringConfirmationValidationRequest
    ) -> ScoringConfirmationValidation:
        current = self.preview_service.preview(
            ScoringPreviewRequest(
                project_id=request.project_id,
                instrument_id=request.instrument_id,
                scoring_rule_id=request.scoring_rule_id,
            )
        )
        if not compare_digest(request.preview_fingerprint, current.fingerprint):
            raise StaleScoringPreviewError(
                "La previsualización cambió; genera una nueva antes de confirmar."
            )
        return ScoringConfirmationValidation(preview=current)
