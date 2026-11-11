"""C7 canonical contracts; provider output is deliberately a much smaller language."""

from typing import Annotated, Literal
from uuid import UUID

from pydantic import AwareDatetime, Field, StrictBool, StrictInt, StrictStr

from app.shared.analysis_v2 import ID, Hash, SourceRef, V2Model

Stage = Literal["home", "context", "data", "analysis", "results"]
UpdateField = Literal[
    "research_question", "main_objective", "study_description", "data_description", "sampling_notes"
]


class TutorSelectionV2(V2Model):
    stage: Stage = "home"
    dataset_id: ID | None = None
    intent_id: ID | None = None
    plan_id: ID | None = None
    result_id: ID | None = None


class TutorActionV2(V2Model):
    kind: Literal["open", "propose_update", "request_diagnostic", "request_proposal"]
    resource_id: ID | None = None
    label: Annotated[str, Field(max_length=300)]
    destination: Literal["home", "context", "datasets", "analysis", "results", "instrument"]
    scope: Annotated[str, Field(max_length=600)] = ""


class TutorContextV2(V2Model):
    schema_version: Literal["2.0.0"] = "2.0.0"
    project_id: ID
    stage: Stage
    context_fingerprint: Hash
    source_refs: list[SourceRef]
    confirmed_summary: dict[str, str]
    pending_questions: list[str]
    data_summary: list[dict[str, str | int | bool | None]]
    intent_summary: dict[str, str | int | bool | None]
    current_plan_ref: SourceRef | None = None
    current_result_ref: SourceRef | None = None
    historical_refs: list[SourceRef]
    allowed_actions: list[TutorActionV2]
    warnings: list[str]


class MessageDraftV2(TutorSelectionV2):
    stage: Stage = Field(...)
    content: Annotated[StrictStr, Field(min_length=1, max_length=16000)]
    request_id: UUID
    external_ai_consent: Literal[True]
    consent_scope: Literal["tutor_context_v3"]
    consent_revision: Annotated[int, Field(strict=True, ge=1)]


class TutorConsentV2(V2Model):
    expected_revision: Annotated[int, Field(strict=True, ge=0)]
    granted: StrictBool
    consent_scope: Literal["tutor_context_v3"]


class TutorUpdateV2(V2Model):
    field: UpdateField
    value: Annotated[StrictStr, Field(min_length=1, max_length=1500)]


class TutorAnswerV2(V2Model):
    explanation: Annotated[StrictStr, Field(min_length=1, max_length=3500)]
    metric_keys: list[Annotated[StrictStr, Field(pattern=r"^m[0-9]{1,3}$")]] = Field(
        default_factory=list, max_length=25
    )
    action_indices: list[Annotated[StrictInt, Field(ge=0, le=20)]] = Field(
        default_factory=list, max_length=6
    )
    updates: list[TutorUpdateV2] = Field(default_factory=list, max_length=3)


class ResultExplanationV2(V2Model):
    schema_version: Literal["2.0.0"] = "2.0.0"
    id: ID
    project_id: ID
    revision: Annotated[int, Field(strict=True, ge=1)]
    result_ref: SourceRef
    context_fingerprint: Hash
    text: Annotated[str, Field(min_length=1, max_length=3500)]
    metric_keys: list[str]
    source: Literal["ai"] = "ai"
    review_status: Literal["draft", "reviewed"] = "draft"
    created_at: AwareDatetime
    reviewed_at: AwareDatetime | None = None


class ExplanationReviewV2(V2Model):
    expected_revision: Annotated[int, Field(strict=True, ge=1)]
    text: Annotated[StrictStr, Field(min_length=1, max_length=3500)]
    confirm: Literal[True]


TUTOR_MODELS = (
    TutorContextV2,
    MessageDraftV2,
    TutorSelectionV2,
    TutorConsentV2,
    ResultExplanationV2,
    ExplanationReviewV2,
)
