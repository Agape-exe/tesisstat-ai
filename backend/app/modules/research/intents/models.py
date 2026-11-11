from typing import Annotated, Literal

from pydantic import Field, StrictBool

from app.shared.analysis_v2 import (
    ID,
    Alternative,
    IntentRole,
    Observations,
    PairedColumns,
    Text,
    V2Model,
)
from app.shared.diagnostics_v2 import CheckName


class ConditionChanges(V2Model):
    same_construct: Literal["yes", "no", "unknown"] | None = None
    linearity: Literal["yes", "no", "unknown"] | None = None
    monotonicity: Literal["yes", "no", "unknown"] | None = None
    comparable_group_shapes: Literal["yes", "no", "unknown"] | None = None
    difference_symmetry: Literal["yes", "no", "unknown"] | None = None
    pooled_variance_justified: Literal["yes", "no", "unknown"] | None = None
    inference_reviewed: Literal["yes", "no", "unknown"] | None = None
    influence_reviewed: Literal["yes", "no", "unknown"] | None = None
    sampling_limit_accepted: Literal["yes", "no", "unknown"] | None = None
    review_notes: Text | None = None


class IntentChanges(V2Model):
    instrument_id: ID | None = None
    instrument_revision: Annotated[int, Field(strict=True, ge=1)] | None = None
    mapping_revision: Annotated[int, Field(strict=True, ge=1)] | None = None
    scoring_rule_id: ID | None = None
    reliability_group: Text | None = None
    objective_id: ID | None = None
    hypothesis_id: ID | None = None
    requested_technique: ID | None = None
    conditions: ConditionChanges | None = None
    kind: Literal["descriptive", "association", "comparison", "reliability", "unknown"] | None = (
        None
    )
    question: Text | None = None
    dataset_id: ID | None = None
    variable_ids: list[ID] | None = Field(default=None, max_length=200)
    roles: list[IntentRole] | None = Field(default=None, max_length=200)
    observations: Observations | None = None
    observational_unit: Text | None = None
    identification: Text | None = None
    comparison_notes: Text | None = None
    linkage: Literal["same_row", "unavailable", "unknown"] | None = None
    identifier_column_id: ID | None = None
    paired_columns: PairedColumns | None = None
    group_column_id: ID | None = None
    alternative: Alternative | None = None
    alpha: Annotated[float, Field(gt=0, lt=1)] | None = None
    estimand: (
        Literal[
            "summary",
            "linear_association",
            "monotonic_association",
            "mean_difference",
            "distribution_difference",
            "internal_consistency",
            "unknown",
        ]
        | None
    ) = None
    missing_policy: Literal["complete_cases"] | None = None


class IntentPatch(V2Model):
    expected_revision: Annotated[int, Field(strict=True, ge=0)]
    changes: IntentChanges
    confirm: StrictBool = False


class DiagnosticRequest(V2Model):
    intent_id: ID
    intent_revision: Annotated[int, Field(strict=True, ge=1)]
    dataset_id: ID
    dataset_revision: Annotated[int, Field(strict=True, ge=1)]
    checks: list[CheckName] = Field(min_length=1, max_length=7)
    confirm: Literal[True]
