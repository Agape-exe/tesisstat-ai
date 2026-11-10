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


class IntentChanges(V2Model):
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
