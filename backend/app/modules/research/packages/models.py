from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.modules.research.datasets.models import Dataset
from app.modules.research.methodology.models import MethodologyReview
from app.shared.contracts import ResearchPackage


class LocalModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class VariableLink(LocalModel):
    variable_id: UUID
    columns: list[str] = Field(default_factory=list)
    role: Literal["independent", "dependent", "covariate", "descriptive", "unknown"] = "unknown"
    measurement_scale: Literal["nominal", "ordinal", "interval", "ratio", "unknown"] = "unknown"


class HypothesisLink(LocalModel):
    id: UUID
    source: str  # general or specific:<zero-based index>
    objective: str = ""  # explicit text selected by the student
    variable_ids: list[UUID] = Field(default_factory=list)
    kind: Literal["association", "comparison", "prediction", "descriptive", "unknown"] = "unknown"
    alternative: Literal["two-sided", "greater", "less", "unspecified"] = "unspecified"
    null_statement: str | None = None


class PackageConfiguration(LocalModel):
    version: int = Field(default=0, ge=0)
    document_id: UUID | None = None
    review_version: int | None = None
    review_hash: str | None = None
    dataset_id: UUID | None = None
    dataset_hash: str | None = None
    design: Literal["experimental", "quasi_experimental", "observational", "unknown"] = "unknown"
    observations: Literal["independent", "paired", "repeated", "unknown"] = "unknown"
    sampling_notes: str = ""
    variables: list[VariableLink] = Field(default_factory=list)
    hypotheses: list[HypothesisLink] = Field(default_factory=list)
    updated_at: datetime | None = None


class ValidationStatus(LocalModel):
    state: Literal["incomplete", "warnings", "ready", "generated", "stale"]
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    configuration: PackageConfiguration
    documents: list[dict] = Field(default_factory=list)
    dataset: Dataset | None = None
    review: MethodologyReview | None = None
    package_id: str | None = None


class StoredPackage(LocalModel):
    project_id: UUID
    configuration: PackageConfiguration
    package: ResearchPackage | None = None
    warnings: list[str] = Field(default_factory=list)
    built_at: datetime | None = None
    built_configuration_version: int | None = None
    validation_state: str | None = None
    validation_errors: list[str] = Field(default_factory=list)
    validation_warnings: list[str] = Field(default_factory=list)
    validated_at: datetime | None = None
