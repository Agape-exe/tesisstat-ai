"""C6 canonical contracts. No documentary methodology is required by v2."""

from typing import Annotated, Literal
from uuid import UUID

from pydantic import AwareDatetime, Field, StrictBool, model_validator

from app.shared.analysis_v2 import ID, Confirmation, Hash, Revision, SourceRef, V2Model
from app.shared.data_sources_v2 import Count
from app.shared.data_workspace_v2 import ColumnLineageV2, DatasetRefV2
from app.shared.instrument_contracts import (
    InstrumentContext,
    InstrumentDimension,
    InstrumentIndicator,
    InstrumentItem,
    ScoringRule,
)


class InstrumentVariableV2(V2Model):
    variable_id: UUID
    name: Annotated[str, Field(min_length=1, max_length=200)]
    scale: Literal["nominal", "ordinal", "interval", "ratio", "unknown"] = "unknown"
    context_variable_id: ID | None = None


class ScoringRuleV2(V2Model):
    scoring_rule_id: UUID
    scope: Literal["dimension", "instrument"]
    dimension_id: UUID | None = None
    item_ids: list[UUID] = Field(min_length=1, max_length=200)
    aggregation: Literal["sum", "mean"]
    missing_policy: Literal["all_required"] = "all_required"


class InstrumentStructureV2(V2Model):
    variables: list[InstrumentVariableV2] = Field(min_length=1, max_length=100)
    dimensions: list[InstrumentDimension] = Field(min_length=1, max_length=100)
    indicators: list[InstrumentIndicator] = Field(min_length=1, max_length=200)
    items: list[InstrumentItem] = Field(min_length=1, max_length=200)
    scoring_rules: list[ScoringRuleV2] = Field(default_factory=list, max_length=100)

    @model_validator(mode="after")
    def integrity(self):
        # Reuse the v1 structural invariants only, as an unconfirmed structure.
        # No legacy provenance, methodology review or hypothesis is manufactured.
        from datetime import UTC, datetime
        from uuid import uuid4

        InstrumentContext(
            instrument_id=uuid4(),
            project_id=uuid4(),
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            variables=[
                {k: v for k, v in x.model_dump().items() if k != "context_variable_id"}
                for x in self.variables
            ],
            dimensions=self.dimensions,
            indicators=self.indicators,
            items=self.items,
            scoring_rules=[ScoringRule(**r.model_dump()) for r in self.scoring_rules],
        )
        for rule in self.scoring_rules:
            if len(set(rule.item_ids)) != len(rule.item_ids):
                raise ValueError("No repitas ítems en una regla.")
        return self


ContextField = Literal[
    "research_question", "main_objective", "study_description", "data_description"
]


class InstrumentProvenanceV2(V2Model):
    source_kind: Literal["manual", "document"] = "manual"
    context_ref: SourceRef
    context_field: ContextField
    source_document_ref: SourceRef | None = None
    legacy_methodology_ref: SourceRef | None = None

    @model_validator(mode="after")
    def refs(self):
        if self.context_ref.kind != "context":
            raise ValueError("Se requiere contexto pertinente.")
        if (self.source_kind == "document") != (self.source_document_ref is not None):
            raise ValueError("La procedencia documental requiere documento.")
        return self


class InstrumentContextV2(InstrumentStructureV2):
    schema_version: Literal["2.0.0"] = "2.0.0"
    instrument_id: ID
    project_id: ID
    revision: Revision
    created_at: AwareDatetime
    updated_at: AwareDatetime
    status: Literal["draft", "reviewed", "stale"] = "draft"
    confirmation: Confirmation | None = None
    provenance: InstrumentProvenanceV2 | None = None
    context_field: ContextField = "study_description"

    @model_validator(mode="after")
    def reviewed(self):
        if self.status == "reviewed" and (not self.confirmation or not self.provenance):
            raise ValueError("Revisar requiere contexto y confirmación.")
        if self.status == "draft" and self.confirmation:
            raise ValueError("Un borrador no está confirmado.")
        return self


class InstrumentEdit(V2Model):
    expected_revision: Annotated[int, Field(strict=True, ge=0)]
    structure: InstrumentStructureV2
    context_field: ContextField = "study_description"


class InstrumentConfirm(V2Model):
    expected_revision: Revision
    confirm: Literal[True]


class ItemColumnV2(V2Model):
    item_id: UUID
    column_id: ID


class MappingEdit(V2Model):
    expected_revision: Annotated[int, Field(strict=True, ge=0)]
    instrument_revision: Revision
    dataset_id: ID
    dataset_revision: Revision
    item_columns: list[ItemColumnV2] = Field(default_factory=list, max_length=200)
    confirm: StrictBool = False

    @model_validator(mode="after")
    def unique(self):
        if len({m.item_id for m in self.item_columns}) != len(self.item_columns) or len(
            {m.column_id for m in self.item_columns}
        ) != len(self.item_columns):
            raise ValueError("La correspondencia entre ítems y columnas debe ser uno a uno.")
        return self


class InstrumentMappingV2(V2Model):
    schema_version: Literal["2.0.0"] = "2.0.0"
    id: ID
    project_id: ID
    revision: Revision
    instrument_ref: SourceRef
    dataset_ref: DatasetRefV2
    dictionary_ref: SourceRef
    item_columns: list[ItemColumnV2]
    status: Literal["draft", "confirmed", "stale"]
    confirmation: Confirmation | None = None

    @model_validator(mode="after")
    def coherent(self):
        if self.instrument_ref.kind != "instrument" or self.dictionary_ref.kind != "dictionary":
            raise ValueError("Referencias de instrumento y diccionario inválidas.")
        if self.dataset_ref.project_id != self.project_id:
            raise ValueError("La tabla pertenece a otro proyecto.")
        if len({m.item_id for m in self.item_columns}) != len(self.item_columns) or len(
            {m.column_id for m in self.item_columns}
        ) != len(self.item_columns):
            raise ValueError("La correspondencia debe ser uno a uno.")
        if self.status == "confirmed" and (not self.confirmation or not self.item_columns):
            raise ValueError("La correspondencia requiere confirmación.")
        return self


class ScorePreviewRequest(V2Model):
    expected_revision: Revision
    mapping_revision: Revision
    scoring_rule_id: UUID
    column_name: Annotated[str, Field(min_length=1, max_length=128)] = "puntuacion"
    confirm: Literal[True]


class ScoreCountsV2(V2Model):
    total: Count
    valid: Count
    missing: Count
    unknown: Count = 0
    out_of_range: Count = 0

    @model_validator(mode="after")
    def coherent(self):
        if any(v > self.total for v in (self.valid, self.missing, self.unknown, self.out_of_range)):
            raise ValueError("Los conteos exceden las filas.")
        if self.total - self.valid > self.missing + self.unknown + self.out_of_range:
            raise ValueError("Falta explicar filas sin puntuación.")
        return self


class ScorePreviewV2(V2Model):
    schema_version: Literal["2.0.0"] = "2.0.0"
    id: ID
    project_id: ID
    revision: Literal[1] = 1
    instrument_id: ID
    source_refs: list[SourceRef]
    fingerprint: Hash
    expires_at: AwareDatetime
    scoring_engine_version: ID
    rule_id: UUID
    counts: ScoreCountsV2
    column_name: str
    bounded_preview: list[float | None] = Field(max_length=20)
    warnings: list[str]
    exclusions: list[str] = Field(max_length=20)


class ScoreConfirm(V2Model):
    preview_id: ID
    fingerprint: Hash
    confirm: Literal[True]
    request_id: UUID


class ScoreRecordV2(V2Model):
    schema_version: Literal["2.0.0"] = "2.0.0"
    id: ID
    project_id: ID
    revision: Literal[1] = 1
    source_refs: list[SourceRef]
    rule_id: UUID
    engine_version: ID
    fingerprint: Hash
    derived_dataset_ref: DatasetRefV2
    derived_column_id: ID
    counts: ScoreCountsV2
    confirmed_by: ID
    confirmed_at: AwareDatetime


class ScoreDerivedTableV2(V2Model):
    """Explicit TableReadPort publication extension; not a prepare/join recipe."""

    schema_version: Literal["2.0.0"] = "2.0.0"
    id: ID
    project_id: ID
    revision: Literal[1] = 1
    hash: Hash
    dataset_ref: DatasetRefV2
    preview_id: ID
    score_id: ID
    source_table_id: ID
    source_refs: list[SourceRef]
    column_lineage: list[ColumnLineageV2]
    row_lineage: list[dict[str, Count | None]]


INSTRUMENT_MODELS = (
    InstrumentContextV2,
    InstrumentMappingV2,
    ScorePreviewV2,
    ScoreRecordV2,
    ScoreDerivedTableV2,
    InstrumentEdit,
    InstrumentConfirm,
    MappingEdit,
    ScorePreviewRequest,
    ScoreConfirm,
)
