"""External, untrusted format; deliberately separate from persisted C2 Facts."""

from typing import Annotated, Literal

from pydantic import AwareDatetime, Field, StrictStr, model_validator

from app.modules.research.context.models import InputText
from app.shared.analysis_v2 import Alternative, Design, Observations, ProjectContextV2, V2Model

LocalRef = Annotated[StrictStr, Field(pattern=r"^[a-zA-Z][a-zA-Z0-9_-]{0,39}$")]


class ImportObjective(V2Model):
    ref: LocalRef
    text: Annotated[StrictStr, Field(min_length=1, max_length=2000)]


class ImportHypothesis(V2Model):
    ref: LocalRef
    statement: Annotated[StrictStr, Field(min_length=1, max_length=2000)]
    objective_ref: LocalRef | None = None
    alternative: Alternative = "unspecified"


class ContextImport(V2Model):
    format_version: Literal["context-import-1.0"]
    title: Annotated[StrictStr, Field(min_length=1, max_length=200)] | None = None
    research_question: InputText | None = None
    main_objective: InputText | None = None
    specific_objectives: list[ImportObjective] = Field(default_factory=list, max_length=40)
    hypotheses: list[ImportHypothesis] = Field(default_factory=list, max_length=40)
    study_description: InputText | None = None
    data_description: InputText | None = None
    observational_unit: InputText | None = None
    sampling_notes: InputText | None = None
    design: Design = "unknown"
    observations: Observations = "unknown"
    complementary_notes: list[Annotated[StrictStr, Field(min_length=1, max_length=2000)]] = Field(
        default_factory=list, max_length=20
    )

    @model_validator(mode="after")
    def references(self):
        for items, text in ((self.specific_objectives, "text"), (self.hypotheses, "statement")):
            refs = [i.ref for i in items]
            values = [getattr(i, text).casefold() for i in items]
            if len(set(refs)) != len(refs) or len(set(values)) != len(values):
                raise ValueError("Referencias o textos duplicados en la lista")
        refs = {i.ref for i in self.specific_objectives}
        if any(h.objective_ref and h.objective_ref not in refs for h in self.hypotheses):
            raise ValueError("Una hipótesis refiere a un objetivo ausente")
        if len(set(n.casefold() for n in self.complementary_notes)) != len(
            self.complementary_notes
        ):
            raise ValueError("Notas duplicadas")
        return self


class SuggestionCreate(V2Model):
    response: Annotated[StrictStr, Field(min_length=1, max_length=120000)]
    expected_revision: Annotated[int, Field(strict=True, ge=0)]


class SuggestionApply(V2Model):
    expected_revision: Annotated[int, Field(strict=True, ge=0)]
    selected_fields: list[Annotated[StrictStr, Field(max_length=100)]] = Field(
        min_length=1, max_length=108
    )
    proposal: ContextImport
    confirm: bool = Field(strict=True, default=False)


class ContextSuggestion(V2Model):
    id: str
    project_id: str
    base_revision: int
    created_at: AwareDatetime
    format_version: Literal["context-import-1.0"] = "context-import-1.0"
    provenance: Literal["ai_suggestion"] = "ai_suggestion"
    state: Literal["pending", "applied", "rejected", "stale"] = "pending"
    proposal: ContextImport
    additional_fields: list[str] = Field(default_factory=list)
    applied_proposal: ContextImport | None = None
    selected_fields: list[str] = Field(default_factory=list)
    result: ProjectContextV2 | None = None
    applied_by: str | None = None

    @model_validator(mode="after")
    def receipt(self):
        if self.state == "applied":
            if not (
                self.result and self.applied_proposal and self.selected_fields and self.applied_by
            ):
                raise ValueError("Applied suggestion requires a complete server receipt")
            if (
                self.result.project_id != self.project_id
                or self.result.revision != self.base_revision + 1
            ):
                raise ValueError("Receipt must match project and next context revision")
        elif self.result or self.applied_proposal or self.selected_fields or self.applied_by:
            raise ValueError("Only applied suggestions have a receipt")
        return self


IMPORT_MODELS = (ContextImport, ContextSuggestion, SuggestionCreate, SuggestionApply)
