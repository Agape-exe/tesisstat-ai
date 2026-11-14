"""Canonical v1 boundary models. No module implementation imports are allowed here."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Identifier = str


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    schema_version: Literal["1.0.0"]


class ResearchVariable(Contract):
    id: Identifier = Field(min_length=1)
    name: str = Field(min_length=1)
    role: Literal["independent", "dependent", "covariate", "descriptive", "unknown"]
    measurement_scale: Literal["nominal", "ordinal", "interval", "ratio", "unknown"]
    columns: list[str] = Field(min_length=1)
    dimensions: list[str] = Field(default_factory=list)
    questions: list[str] = Field(default_factory=list)


class ResearchHypothesis(Contract):
    id: Identifier = Field(min_length=1)
    statement: str = Field(min_length=1)
    objective: str = Field(min_length=1)
    kind: Literal["association", "comparison", "prediction", "descriptive", "unknown"]
    variable_ids: list[Identifier] = Field(min_length=1)
    null_statement: str | None = None
    alternative: Literal["two-sided", "greater", "less", "unspecified"] = "unspecified"


class DatasetReference(Contract):
    id: Identifier = Field(min_length=1)
    location: str = Field(
        min_length=1, description="Opaque storage key or fixture path; no secrets"
    )
    format: Literal["csv", "xlsx"]
    row_count: int = Field(ge=0)
    columns: list[str] = Field(min_length=1)
    synthetic: bool


class ResearchPackage(Contract):
    id: Identifier = Field(min_length=1)
    title: str = Field(min_length=1)
    methodology_status: Literal["draft", "reviewed"]
    design: Literal["experimental", "quasi_experimental", "observational", "unknown"]
    observations: Literal["independent", "paired", "repeated", "unknown"]
    sampling_notes: str
    variables: list[ResearchVariable] = Field(min_length=1)
    hypotheses: list[ResearchHypothesis] = Field(min_length=1)
    dataset: DatasetReference
    pending_questions: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_references(self) -> "ResearchPackage":
        variable_ids = [variable.id for variable in self.variables]
        hypothesis_ids = [hypothesis.id for hypothesis in self.hypotheses]
        if len(set(variable_ids)) != len(variable_ids):
            raise ValueError("Variable IDs must be unique")
        if len(set(hypothesis_ids)) != len(hypothesis_ids):
            raise ValueError("Hypothesis IDs must be unique")
        for hypothesis in self.hypotheses:
            if not set(hypothesis.variable_ids) <= set(variable_ids):
                raise ValueError("Hypothesis references an unknown variable")
        for variable in self.variables:
            if not set(variable.columns) <= set(self.dataset.columns):
                raise ValueError("Variable references an unknown dataset column")
        return self


class AnalysisPlan(Contract):
    id: Identifier = Field(min_length=1)
    research_package_id: Identifier = Field(min_length=1)
    hypothesis_id: Identifier = Field(min_length=1)
    dataset_id: Identifier = Field(min_length=1)
    status: Literal["needs_clarification", "proposed", "approved"]
    technique: str | None = None
    rationale: str = Field(min_length=1)
    alpha: float = Field(default=0.05, gt=0, lt=1)
    assumptions_to_check: list[str] = Field(default_factory=list)
    pending_questions: list[str] = Field(default_factory=list)


class Metric(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    name: str = Field(min_length=1)
    value: float


class AssumptionCheck(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1)
    status: Literal["passed", "failed", "not_checked"]
    details: str


class AnalysisResult(Contract):
    id: Identifier = Field(min_length=1)
    analysis_plan_id: Identifier = Field(min_length=1)
    dataset_id: Identifier = Field(min_length=1)
    status: Literal["completed", "failed", "not_executed"]
    metrics: list[Metric] = Field(default_factory=list)
    assumptions: list[AssumptionCheck] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    engine_version: str = Field(min_length=1)
    interpretation: str | None = None


CONTRACT_MODELS = (
    ResearchPackage,
    ResearchHypothesis,
    ResearchVariable,
    DatasetReference,
    AnalysisPlan,
    AnalysisResult,
)
