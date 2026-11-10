"""Canonical C5 contracts. Immutable proposal/result plus application read state."""

from typing import Annotated, Literal
from uuid import UUID

from pydantic import AwareDatetime, Field, StrictBool, model_validator

from app.shared.analysis_v2 import ID, Confirmation, Hash, SourceRef, V2Model
from app.shared.diagnostics_v2 import DiagnosticCheckV2, GroupCountV2

Technique = Literal[
    "descriptive_summary",
    "pearson",
    "spearman",
    "t_welch",
    "t_independent",
    "mann_whitney",
    "t_paired",
    "wilcoxon",
    "cronbach_alpha",
]
CalculationMethod = Literal[
    "pending",
    "descriptive-v2",
    "pearson-two-sided-v2",
    "spearman-two-sided-v2",
    "t_welch-two-sided-v2",
    "t_independent-two-sided-v2",
    "mann_whitney-two-sided-v2",
    "t_paired-two-sided-v2",
    "wilcoxon-two-sided-v2",
    "cronbach_alpha-two-sided-v2",
]


class PlanRequest(V2Model):
    intent_id: ID
    intent_revision: Annotated[int, Field(strict=True, ge=1)]
    dataset_id: ID | None = None
    dataset_revision: Annotated[int, Field(strict=True, ge=1)] | None = None
    diagnostic_ids: list[ID] = Field(default_factory=list, max_length=20)


class ApprovalRequest(V2Model):
    proposal_token: Hash
    confirm: StrictBool


class ExecutionRequest(V2Model):
    proposal_token: Hash
    request_id: UUID


class PlanParameters(V2Model):
    alpha: Annotated[float, Field(gt=0, lt=1)]
    alternative: Literal["two-sided", "greater", "less", "unspecified"]
    missing_policy: Literal["complete_cases"] = "complete_cases"
    calculation_method: CalculationMethod


class PlanQuestion(V2Model):
    code: str
    field: str
    question: str
    destination: Literal["analysis", "datasets", "context", "instrument"] = "analysis"


class PlanAlternative(V2Model):
    technique: Technique
    reason: str


class CaseCounts(V2Model):
    total: Annotated[int, Field(ge=0)]
    used: Annotated[int, Field(ge=0)]
    excluded: Annotated[int, Field(ge=0)]
    groups: list[GroupCountV2] = Field(default_factory=list)
    pairs: Annotated[int, Field(ge=0)] | None = None

    @model_validator(mode="after")
    def consistent(self):
        if self.total != self.used + self.excluded:
            raise ValueError("Case counts must agree")
        return self


class AnalysisPlanV2(V2Model):
    schema_version: Literal["2.0.0"] = "2.0.0"
    id: ID
    project_id: ID
    revision: Literal[1] = 1
    snapshot_ref: SourceRef | None
    intent_id: ID
    dataset_id: ID | None
    status: Literal["needs_clarification", "proposed", "approved"]
    technique: Technique | None
    parameters: PlanParameters
    rationale: str
    evidence_refs: list[SourceRef]
    alternatives: list[PlanAlternative] = Field(default_factory=list)
    pending_questions: list[PlanQuestion] = Field(default_factory=list)
    limitations: list[str]
    source_fingerprint: Hash
    proposal_token: Hash
    created_at: AwareDatetime
    approval: Confirmation | None = None
    question: str
    variable_names: list[str]
    case_counts: CaseCounts | None
    policy_versions: dict[str, str]
    validity: Literal["current", "stale"] = "current"
    invalidated_at: AwareDatetime | None = None
    stale_reasons: list[str] = Field(default_factory=list)
    data_authorization_required: bool = True
    data_authorized: bool = False
    execution_status: Literal["not_started", "running", "completed", "failed"] = "not_started"

    @model_validator(mode="after")
    def eligible(self):
        if self.status in {"proposed", "approved"} and (
            not self.technique or self.pending_questions or not self.snapshot_ref
        ):
            raise ValueError("Eligible plan requires snapshot and no questions")
        if (self.status == "approved") != (self.approval is not None):
            raise ValueError("Approval must match status")
        return self


class ResultMetric(V2Model):
    key: str
    label: str
    value: float | None
    unit: str | None = None
    reason: str | None = None

    @model_validator(mode="after")
    def absent_reason(self):
        if self.value is None and not self.reason:
            raise ValueError("Missing metric requires reason")
        return self


class ResultColumn(V2Model):
    key: str
    label: str
    type: Literal["number", "string"]


class ResultTable(V2Model):
    id: ID
    title: str
    columns: list[ResultColumn]
    rows: list[dict[str, float | str | None]]


class ResultInterpretation(V2Model):
    text: str
    metric_keys: list[str]
    source: Literal["template"] = "template"
    review_status: Literal["draft", "reviewed"] = "draft"


class ResultFigure(V2Model):
    id: ID
    type: str
    source_metric_keys: list[str]
    caption: str


class AnalysisResultV2(V2Model):
    schema_version: Literal["2.0.0"] = "2.0.0"
    id: ID
    project_id: ID
    revision: Literal[1] = 1
    analysis_plan_id: ID
    snapshot_ref: SourceRef
    dataset_id: ID
    status: Literal["completed", "failed", "not_executed"]
    created_at: AwareDatetime
    engine_version: str
    method_version: str
    source_fingerprint: Hash
    source_refs: list[SourceRef]
    case_counts: CaseCounts
    metrics: list[ResultMetric]
    tables: list[ResultTable] = Field(default_factory=list)
    figures: list[ResultFigure] = Field(default_factory=list)
    assumptions: list[DiagnosticCheckV2]
    warnings: list[str]
    limitations: list[str]
    interpretation: ResultInterpretation | None = None
    question: str
    technique: Technique
    variable_names: list[str]
    validity: Literal["current", "stale"] = "current"
    stale_reasons: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def truthful(self):
        if self.status != "completed" and (self.metrics or self.interpretation):
            raise ValueError("Failed calculations cannot contain conclusions")
        keys = [m.key for m in self.metrics]
        if len(keys) != len(set(keys)):
            raise ValueError("Duplicate metrics")
        if self.interpretation and not set(self.interpretation.metric_keys).issubset(keys):
            raise ValueError("Interpretation must cite real metrics")
        return self


ANALYSIS_MODELS = (PlanRequest, ApprovalRequest, ExecutionRequest, AnalysisPlanV2, AnalysisResultV2)
