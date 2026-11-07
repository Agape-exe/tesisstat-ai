"""In-memory scoring previews over authorized instrument data.

This internal orchestration layer coordinates the Research-owned authorization
bridge with the pure Statistics scoring functions. It does not persist results,
create derived datasets, expose endpoints, or simulate human confirmation.
"""

from __future__ import annotations

import hashlib
import json
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.modules.statistics.inferential import StatisticalCalculationError
from app.modules.statistics.scoring import (
    calculate_cronbach_reliability,
    calculate_scores,
    recode_rows,
)
from app.modules.statistics.scoring_context import scoring_inputs_from_context
from app.orchestration.research_statistics import InstrumentStatisticsBridge


class InternalPreviewModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)


class ScoringPreviewRequest(InternalPreviewModel):
    project_id: UUID
    instrument_id: UUID
    scoring_rule_id: UUID


class ScoreCaseCounts(InternalPreviewModel):
    total: int = Field(ge=0)
    valid: int = Field(ge=0)
    missing: int = Field(ge=0)


class ReliabilityPreview(InternalPreviewModel):
    status: Literal["calculated", "not_calculable"]
    alpha: float | None = None
    valid_rows: int = Field(ge=0)
    excluded_rows: int = Field(ge=0)
    reason: str | None = None


class ScoringPreviewPayload(InternalPreviewModel):
    status: Literal["previewed"] = "previewed"
    project_id: UUID
    instrument_id: UUID
    instrument_version: int = Field(ge=0)
    dataset_id: UUID
    dataset_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    scoring_rule_id: UUID
    scores: tuple[float | None, ...]
    score_cases: ScoreCaseCounts
    reliability: ReliabilityPreview
    warnings: tuple[str, ...] = ()


class ScoringPreview(ScoringPreviewPayload):
    fingerprint: str = Field(pattern=r"^[a-f0-9]{64}$")


def _fingerprint(payload: ScoringPreviewPayload) -> str:
    canonical = json.dumps(
        payload.model_dump(mode="json"),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode()
    return hashlib.sha256(canonical).hexdigest()


class InstrumentScoringPreviewService:
    """Build deterministic, non-persistent previews from authorized rows."""

    def __init__(self, bridge: InstrumentStatisticsBridge) -> None:
        self.bridge = bridge

    def preview(self, request: ScoringPreviewRequest) -> ScoringPreview:
        authorized = self.bridge.get_authorized_instrument_data(
            project_id=request.project_id,
            instrument_id=request.instrument_id,
            scoring_rule_id=request.scoring_rule_id,
        )
        context = authorized.context
        mapping = context.dataset_mapping
        assert mapping is not None

        inputs = scoring_inputs_from_context(context, str(request.scoring_rule_id))
        scores = calculate_scores(authorized.rows, inputs.item_specs, inputs.rule)
        recoded = recode_rows(authorized.rows, inputs.item_specs)
        complete_rows = sum(all(value is not None for value in row) for row in recoded)
        excluded_rows = len(recoded) - complete_rows

        warnings: list[str] = []
        if scores.missing_rows:
            warnings.append(
                f"{scores.missing_rows} observaciones no tienen puntuación por valores faltantes."
            )

        try:
            reliability_result = calculate_cronbach_reliability(authorized.rows, inputs.item_specs)
        except StatisticalCalculationError as error:
            reason = str(error)
            reliability = ReliabilityPreview(
                status="not_calculable",
                alpha=None,
                valid_rows=complete_rows,
                excluded_rows=excluded_rows,
                reason=reason,
            )
            warnings.append(f"No se pudo calcular alfa de Cronbach: {reason}")
        else:
            reliability = ReliabilityPreview(
                status="calculated",
                alpha=reliability_result.result.metrics["alpha"],
                valid_rows=reliability_result.valid_rows,
                excluded_rows=reliability_result.excluded_rows,
                reason=None,
            )
            warnings.extend(reliability_result.result.warnings)

        payload = ScoringPreviewPayload(
            project_id=context.project_id,
            instrument_id=context.instrument_id,
            instrument_version=context.version,
            dataset_id=mapping.dataset_id,
            dataset_hash=mapping.dataset_hash,
            scoring_rule_id=request.scoring_rule_id,
            scores=scores.values,
            score_cases=ScoreCaseCounts(
                total=len(authorized.rows),
                valid=scores.valid_rows,
                missing=scores.missing_rows,
            ),
            reliability=reliability,
            warnings=tuple(warnings),
        )
        return ScoringPreview(**payload.model_dump(), fingerprint=_fingerprint(payload))
