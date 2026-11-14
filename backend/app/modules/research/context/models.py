"""Manual HTTP input. Provenance, actor, dates and confirmations are server-only."""

from typing import Annotated

from pydantic import Field, StrictStr

from app.shared.analysis_v2 import ID, Alternative, Design, Observations, V2Model

InputText = Annotated[StrictStr, Field(max_length=2000)]


class ObjectiveInput(V2Model):
    id: ID | None = None
    text: InputText | None


class HypothesisInput(V2Model):
    id: ID | None = None
    statement: InputText | None
    objective_id: ID | None = None
    alternative: Alternative = "unspecified"


class ContextChanges(V2Model):
    research_question: InputText | None = None
    main_objective: InputText | None = None
    specific_objectives: list[ObjectiveInput] | None = Field(default=None, max_length=40)
    hypotheses: list[HypothesisInput] | None = Field(default=None, max_length=40)
    study_description: InputText | None = None
    data_description: InputText | None = None
    observational_unit: InputText | None = None
    sampling_notes: InputText | None = None
    design: Design | None = None
    observations: Observations | None = None
    complementary_notes: list[InputText | None] | None = Field(default=None, max_length=20)


class ContextPatch(V2Model):
    expected_revision: Annotated[int, Field(strict=True, ge=0)]
    changes: ContextChanges = Field(default_factory=ContextChanges)
    confirm_fields: list[Annotated[StrictStr, Field(min_length=1, max_length=200)]] = Field(
        default_factory=list, max_length=120
    )
