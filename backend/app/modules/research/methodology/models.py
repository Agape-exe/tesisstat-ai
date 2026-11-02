from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

Text = Annotated[str, Field(min_length=1, max_length=2000)]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class Finding(StrictModel):
    value: Text | None = None
    kind: Literal["unknown", "quotation", "inference"] = "unknown"
    evidence: list[Text] = Field(default_factory=list, max_length=5)

    @model_validator(mode="after")
    def coherent(self):
        if self.kind == "unknown":
            if self.value is not None or self.evidence:
                raise ValueError("Unknown findings must be empty")
        elif not self.value or not self.value.strip() or not self.evidence:
            raise ValueError("Known findings require a value and evidence")
        return self


Findings = Annotated[list[Finding], Field(max_length=40)]


class VariableDraft(StrictModel):
    name: Finding
    role: Finding = Field(default_factory=Finding)
    measurement_scale: Finding = Field(default_factory=Finding)
    dimensions: Findings = Field(default_factory=list)
    indicators: Findings = Field(default_factory=list)
    instrument_items: Findings = Field(default_factory=list)

    @model_validator(mode="after")
    def conservative(self):
        for finding in (self.role, self.measurement_scale):
            if finding.kind == "inference":
                raise ValueError("Role and scale require explicit evidence or unknown")
        return self


class MethodologyContent(StrictModel):
    title: Finding = Field(default_factory=Finding)
    general_problem: Finding = Field(default_factory=Finding)
    general_objective: Finding = Field(default_factory=Finding)
    specific_objectives: Findings = Field(default_factory=list)
    general_hypothesis: Finding = Field(default_factory=Finding)
    specific_hypotheses: Findings = Field(default_factory=list)
    variables: list[VariableDraft] = Field(default_factory=list, max_length=20)
    research_design: Finding = Field(default_factory=Finding)
    observation_design: Finding = Field(default_factory=Finding)
    additional_methodology: Findings = Field(default_factory=list)
    warnings: list[Text] = Field(default_factory=list, max_length=20)
    questions: list[Text] = Field(default_factory=list, max_length=20)


class SourceReference(BaseModel):
    field: str
    document_id: UUID
    quote: str
    start: int
    end: int


class MethodologyDraft(BaseModel):
    project_id: UUID
    document_id: UUID
    review_status: Literal["unreviewed"] = "unreviewed"
    content: MethodologyContent
    pending_fields: list[str]
    evidence: list[SourceReference]
    warnings: list[str]
    source_hash: str
    model: str
    schema_version: Literal["1"] = "1"
    created_at: datetime


class MethodologyState(BaseModel):
    project_id: UUID
    document_id: UUID
    status: Literal["not_started", "processing", "completed", "failed"] = "not_started"
    provider_configured: bool = False
    attempts: int = 0
    error_code: str | None = None
    message: str | None = None
    retry_after: datetime | None = None
    draft: MethodologyDraft | None = None
