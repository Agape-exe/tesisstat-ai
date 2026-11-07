"""DTOs independientes para el intercambio Research -> Statistics de instrumentos.

Este módulo no modifica los contratos canónicos v1.0.0. Research conserva la
propiedad y persistencia del contexto; Statistics podrá consumir únicamente una
instancia confirmada mediante un puerto acordado en una sesión posterior.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Protocol
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class InstrumentDto(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class HumanConfirmation(InstrumentDto):
    state: Literal["pending", "confirmed"]
    confirmed_at: datetime | None = None
    confirmer_ref: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def require_consistent_confirmation(self) -> HumanConfirmation:
        if self.state == "confirmed" and self.confirmed_at is None:
            raise ValueError("Una confirmación requiere fecha de confirmación.")
        if self.state == "pending" and (
            self.confirmed_at is not None or self.confirmer_ref is not None
        ):
            raise ValueError("Una confirmación pendiente no puede declarar confirmante.")
        return self


class InstrumentProvenance(InstrumentDto):
    source_kind: Literal["document", "manual"]
    source_document_id: UUID | None = None
    source_document_hash: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    methodology_review_id: UUID
    methodology_review_version: int = Field(ge=0)
    methodology_review_hash: str = Field(pattern=r"^[a-f0-9]{64}$")

    @model_validator(mode="after")
    def require_document_provenance_when_declared(self) -> InstrumentProvenance:
        has_document = self.source_document_id is not None
        has_hash = self.source_document_hash is not None
        if has_document != has_hash:
            raise ValueError("La referencia documental requiere ID y hash juntos.")
        if self.source_kind == "document" and not has_document:
            raise ValueError("La procedencia documental requiere documento y hash.")
        return self


class InstrumentVariable(InstrumentDto):
    variable_id: UUID


class InstrumentDimension(InstrumentDto):
    dimension_id: UUID
    variable_id: UUID
    name: str = Field(min_length=1, max_length=200)


class InstrumentIndicator(InstrumentDto):
    indicator_id: UUID
    dimension_id: UUID
    name: str = Field(min_length=1, max_length=200)


class ResponseOption(InstrumentDto):
    code: str = Field(min_length=1, max_length=120)
    label: str = Field(min_length=1, max_length=300)
    numeric_value: float


class InstrumentItem(InstrumentDto):
    item_id: UUID
    variable_id: UUID
    dimension_id: UUID
    indicator_id: UUID
    text: str = Field(min_length=1, max_length=2000)
    response_type: Literal["single_choice", "numeric"]
    response_options: list[ResponseOption] = Field(default_factory=list)
    valid_min: float | None = None
    valid_max: float | None = None
    reverse_scored: bool = False
    reverse_rule: Literal["min_plus_max_minus_value"] | None = None
    provenance: InstrumentProvenance

    @field_validator("response_options")
    @classmethod
    def require_unique_option_codes(cls, value: list[ResponseOption]) -> list[ResponseOption]:
        if len({option.code for option in value}) != len(value):
            raise ValueError("Los códigos de respuesta deben ser únicos por ítem.")
        return value

    @model_validator(mode="after")
    def validate_scoring_metadata(self) -> InstrumentItem:
        if (self.valid_min is None) != (self.valid_max is None):
            raise ValueError("El rango válido requiere mínimo y máximo.")
        if self.valid_min is not None and self.valid_min >= self.valid_max:
            raise ValueError("El mínimo válido debe ser menor que el máximo.")
        if self.response_type == "single_choice" and len(self.response_options) < 2:
            raise ValueError("Un ítem de opción única requiere al menos dos opciones.")
        if self.response_type == "numeric" and self.response_options:
            raise ValueError("Un ítem numérico no define opciones codificadas.")
        if self.reverse_scored:
            if self.reverse_rule != "min_plus_max_minus_value":
                raise ValueError("Un ítem invertido requiere una regla de inversión explícita.")
            if self.valid_min is None or self.valid_max is None:
                raise ValueError("Un ítem invertido requiere extremos de escala confirmados.")
        elif self.reverse_rule is not None:
            raise ValueError("La regla de inversión solo corresponde a ítems invertidos.")
        if self.valid_min is not None:
            for option in self.response_options:
                if not self.valid_min <= option.numeric_value <= self.valid_max:
                    raise ValueError("La codificación de una opción está fuera del rango válido.")
        return self


class ScoringRule(InstrumentDto):
    scoring_rule_id: UUID
    scope: Literal["dimension", "instrument"]
    dimension_id: UUID | None = None
    item_ids: list[UUID] = Field(min_length=1)
    aggregation: Literal["sum", "mean"]
    missing_policy: Literal["all_required"]
    confirmed: bool

    @model_validator(mode="after")
    def require_scope_target(self) -> ScoringRule:
        if (self.scope == "dimension") != (self.dimension_id is not None):
            raise ValueError("Una regla por dimensión debe declarar exactamente una dimensión.")
        if len(set(self.item_ids)) != len(self.item_ids):
            raise ValueError("Los ítems de una regla de puntuación deben ser únicos.")
        return self


class ItemColumnMapping(InstrumentDto):
    item_id: UUID
    column_name: str = Field(min_length=1, max_length=255)


class DatasetMapping(InstrumentDto):
    dataset_id: UUID
    dataset_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    instrument_version: int = Field(ge=1)
    status: Literal["draft", "confirmed", "stale"]
    confirmation: HumanConfirmation
    item_columns: list[ItemColumnMapping] = Field(default_factory=list)

    @model_validator(mode="after")
    def require_confirmation_for_confirmed_mapping(self) -> DatasetMapping:
        if self.status == "confirmed" and self.confirmation.state != "confirmed":
            raise ValueError("Un mapeo confirmado requiere confirmación humana.")
        if self.status == "draft" and self.confirmation.state != "pending":
            raise ValueError("Un mapeo en borrador no puede estar confirmado.")
        if len({mapping.item_id for mapping in self.item_columns}) != len(self.item_columns):
            raise ValueError("Cada ítem puede vincularse a una sola columna por mapeo.")
        if len({mapping.column_name for mapping in self.item_columns}) != len(self.item_columns):
            raise ValueError("Una columna no puede representar dos ítems en el mismo mapeo.")
        return self


class InstrumentContextReader(Protocol):
    """Read a confirmed context through Research's authorized boundary."""

    def get_confirmed_context(self, project_id: str, instrument_id: str) -> InstrumentContext: ...


class InstrumentContext(InstrumentDto):
    schema_version: Literal["1.0.0"]
    instrument_id: UUID
    project_id: UUID
    research_package_id: UUID | None = None
    version: int = Field(ge=1)
    status: Literal["draft", "reviewed", "stale"]
    created_at: datetime
    updated_at: datetime
    provenance: InstrumentProvenance
    confirmation: HumanConfirmation
    variables: list[InstrumentVariable] = Field(min_length=1)
    dimensions: list[InstrumentDimension] = Field(min_length=1)
    indicators: list[InstrumentIndicator] = Field(min_length=1)
    items: list[InstrumentItem] = Field(min_length=1)
    scoring_rules: list[ScoringRule] = Field(min_length=1)
    dataset_mapping: DatasetMapping | None = None

    @model_validator(mode="after")
    def validate_relationships_and_lifecycle(self) -> InstrumentContext:
        if self.updated_at < self.created_at:
            raise ValueError("La fecha de actualización no puede preceder a la creación.")
        if len({variable.variable_id for variable in self.variables}) != len(self.variables):
            raise ValueError("Las variables del instrumento deben ser únicas.")
        if len({dimension.dimension_id for dimension in self.dimensions}) != len(self.dimensions):
            raise ValueError("Las dimensiones del instrumento deben ser únicas.")
        if len({indicator.indicator_id for indicator in self.indicators}) != len(self.indicators):
            raise ValueError("Los indicadores del instrumento deben ser únicos.")
        if len({item.item_id for item in self.items}) != len(self.items):
            raise ValueError("Los ítems del instrumento deben ser únicos.")
        if len({rule.scoring_rule_id for rule in self.scoring_rules}) != len(self.scoring_rules):
            raise ValueError("Las reglas de puntuación deben ser únicas.")

        variable_ids = {variable.variable_id for variable in self.variables}
        dimensions = {dimension.dimension_id: dimension for dimension in self.dimensions}
        indicators = {indicator.indicator_id: indicator for indicator in self.indicators}
        items = {item.item_id: item for item in self.items}
        if not {dimension.variable_id for dimension in self.dimensions} <= variable_ids:
            raise ValueError("Una dimensión referencia una variable inexistente.")
        if not {indicator.dimension_id for indicator in self.indicators} <= set(dimensions):
            raise ValueError("Un indicador referencia una dimensión inexistente.")
        for item in self.items:
            dimension = dimensions.get(item.dimension_id)
            indicator = indicators.get(item.indicator_id)
            if dimension is None or indicator is None:
                raise ValueError("Un ítem requiere dimensión e indicador existentes.")
            if (
                item.variable_id != dimension.variable_id
                or indicator.dimension_id != item.dimension_id
            ):
                raise ValueError("La jerarquía variable dimensión indicador ítem no es coherente.")
        for rule in self.scoring_rules:
            if not set(rule.item_ids) <= set(items):
                raise ValueError("Una regla de puntuación referencia ítems inexistentes.")
            if rule.scope == "dimension":
                assert rule.dimension_id is not None
                if rule.dimension_id not in dimensions:
                    raise ValueError(
                        "Una regla por dimensión referencia una dimensión inexistente."
                    )
                if any(
                    items[item_id].dimension_id != rule.dimension_id for item_id in rule.item_ids
                ):
                    raise ValueError(
                        "Una regla por dimensión solo puede usar ítems de esa dimensión."
                    )
        if self.status == "reviewed":
            if self.confirmation.state != "confirmed" or not all(
                rule.confirmed for rule in self.scoring_rules
            ):
                raise ValueError(
                    "Un instrumento revisado requiere confirmación y reglas confirmadas."
                )
        if self.status == "draft" and self.confirmation.state != "pending":
            raise ValueError("Un instrumento en borrador no puede estar confirmado.")
        if self.dataset_mapping is not None:
            if self.dataset_mapping.instrument_version != self.version:
                raise ValueError("El mapeo debe corresponder a la versión actual del instrumento.")
            mapped = {mapping.item_id for mapping in self.dataset_mapping.item_columns}
            if not mapped <= set(items):
                raise ValueError("El mapeo referencia ítems inexistentes.")
            if self.dataset_mapping.status == "confirmed" and mapped != set(items):
                raise ValueError(
                    "Un mapeo confirmado debe vincular todos los ítems del instrumento."
                )
        return self
