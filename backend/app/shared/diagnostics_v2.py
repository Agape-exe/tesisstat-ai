"""C4 diagnostic evidence: immutable payload, freshness is a read projection."""

from typing import Annotated, Literal

from pydantic import AwareDatetime, Field

from app.shared.analysis_v2 import ID, SourceRef, V2Model

CheckName = Literal[
    "complete_cases",
    "group_sizes",
    "paired_cases",
    "distribution",
    "normality",
    "homogeneity",
    "influence",
]
Count = Annotated[int, Field(ge=0)]


class DiagnosticScopeV2(V2Model):
    column_ids: list[ID]
    checks: list[CheckName]
    missing_policy: Literal["complete_cases"] = "complete_cases"
    alpha: Annotated[float, Field(gt=0, lt=1)]


class DiagnosticCheckV2(V2Model):
    name: CheckName
    method: str
    method_version: str
    target: str
    case_count: Count
    statistic: float | None = None
    p_value: Annotated[float, Field(ge=0, le=1)] | None = None
    status: Literal["compatible", "incompatible", "not_checked"]
    details: Annotated[str, Field(min_length=1)]


class GroupCountV2(V2Model):
    label: str
    count: Count


class AnalysisProfileV2(V2Model):
    total_rows: Count
    complete_case_count: Count
    excluded_count: Count
    excluded_missing_count: Count
    excluded_invalid_count: Count
    group_counts: list[GroupCountV2] = Field(default_factory=list)
    complete_pair_count: Count | None = None
    zero_difference_count: Count | None = None
    warnings: list[str] = Field(default_factory=list)


class DiagnosticFigureV2(V2Model):
    kind: Literal["histogram", "qq", "scatter"]
    target: str
    x_label: str
    y_label: str
    x: list[float]
    y: list[float]
    details: str


class DiagnosticV2(V2Model):
    schema_version: Literal["2.0.0"] = "2.0.0"
    id: ID
    project_id: ID
    revision: Literal[1] = 1
    source_refs: list[SourceRef]
    created_at: AwareDatetime
    intent_id: ID
    scope: DiagnosticScopeV2
    status: Literal["completed", "not_calculable", "failed"]
    algorithm_version: str
    engine_version: str
    checks: list[DiagnosticCheckV2]
    warnings: list[str]
    profile: AnalysisProfileV2
    figures: list[DiagnosticFigureV2] = Field(default_factory=list)
    state: Literal["current", "stale"] = "current"
    stale_reason: str | None = None


DIAGNOSTIC_MODELS = (DiagnosticV2,)
