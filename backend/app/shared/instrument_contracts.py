"""Canonical v1 boundary models and domain definitions for InstrumentContext v1.0.0.

No module implementation imports (research/statistics internal services or repositories)
are allowed here. This module is the single source of truth for the public contract
exchanged between Research and Statistics.
"""

from __future__ import annotations

import math
import re
from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

Sha256Hex = Annotated[
    str,
    StringConstraints(
        pattern=r"^[a-f0-9]{64}$",
        strip_whitespace=True,
    ),
]

_PII_COLUMN_PATTERN = re.compile(
    r"(^|[\W_])(id|dni|nombre|nombres|apellido|apellidos|correo|email|"
    r"e_mail|name|surname|telefono|phone|direccion|address|codigo|uuid)([\W_]|$)",
    re.I,
)


def is_pii_column(name: str) -> bool:
    cleaned = name.strip()
    return bool(
        _PII_COLUMN_PATTERN.search(cleaned) or "@" in cleaned or bool(re.search(r"\d{8,}", cleaned))
    )


class StrictDomainModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        validate_default=True,
        str_strip_whitespace=True,
    )


class ResponseOption(StrictDomainModel):
    code: str = Field(min_length=1, max_length=100)
    label: str = Field(min_length=1, max_length=200)
    numeric_value: float

    @field_validator("numeric_value")
    @classmethod
    def validate_numeric_finite(cls, v: float) -> float:
        if not math.isfinite(v):
            raise ValueError("numeric_value debe ser un número finito (no NaN ni infinito).")
        return v


class InstrumentItem(StrictDomainModel):
    item_id: UUID
    variable_id: UUID
    dimension_id: UUID
    indicator_id: UUID
    text: str = Field(min_length=1, max_length=1000)
    response_type: Literal["single_choice", "numeric"]
    response_options: list[ResponseOption] = Field(default_factory=list)
    valid_min: float | None = None
    valid_max: float | None = None
    reverse_scored: bool = False
    reverse_rule: Literal["min_plus_max_minus_value"] | None = None
    source_quote: str | None = Field(default=None, max_length=1000)

    @field_validator("valid_min", "valid_max")
    @classmethod
    def validate_bounds_finite(cls, v: float | None) -> float | None:
        if v is not None and not math.isfinite(v):
            raise ValueError("Los límites válidos deben ser números finitos (no NaN ni infinito).")
        return v

    @model_validator(mode="after")
    def validate_item_coherence(self) -> InstrumentItem:
        if self.response_type == "single_choice":
            if len(self.response_options) < 2:
                raise ValueError(
                    "Los ítems single_choice requieren al menos dos alternativas de respuesta."
                )
            codes = [opt.code.strip() for opt in self.response_options]
            if len(set(codes)) != len(codes):
                raise ValueError("Las alternativas de respuesta deben tener códigos únicos.")
            labels = [opt.label.strip().lower() for opt in self.response_options]
            if len(set(labels)) != len(labels):
                raise ValueError(
                    "Las alternativas de respuesta deben tener etiquetas descriptivas únicas."
                )
            numeric_vals = [opt.numeric_value for opt in self.response_options]
            if len(set(numeric_vals)) != len(numeric_vals):
                raise ValueError(
                    "Las alternativas de respuesta deben tener valores numéricos únicos."
                )
        elif self.response_type == "numeric":
            if self.response_options:
                raise ValueError(
                    "Los ítems de tipo numeric no deben declarar opciones de selección categórica."
                )

        if self.valid_min is not None and self.valid_max is not None:
            if self.valid_min >= self.valid_max:
                raise ValueError("valid_min debe ser estrictamente menor que valid_max.")

        # Validación de coherencia interna: los numeric_value de response_options
        # deben respetar los límites valid_min / valid_max declarados para el ítem
        for opt in self.response_options:
            if self.valid_min is not None and opt.numeric_value < self.valid_min:
                raise ValueError(
                    f"La opción '{opt.code}' con valor numérico {opt.numeric_value} "
                    f"es inferior al límite valid_min ({self.valid_min})."
                )
            if self.valid_max is not None and opt.numeric_value > self.valid_max:
                raise ValueError(
                    f"La opción '{opt.code}' con valor numérico {opt.numeric_value} "
                    f"supera el límite valid_max ({self.valid_max})."
                )

        if self.reverse_scored:
            if self.reverse_rule != "min_plus_max_minus_value":
                raise ValueError(
                    "Los ítems con puntuación invertida requieren la regla explícita "
                    "'min_plus_max_minus_value'."
                )
            if self.valid_min is None or self.valid_max is None:
                raise ValueError(
                    "Los ítems con puntuación invertida requieren declarar explícitamente "
                    "valid_min y valid_max."
                )
        else:
            if self.reverse_rule is not None:
                raise ValueError(
                    "Los ítems no invertidos no deben declarar una regla de inversión."
                )

        return self


class InstrumentIndicator(StrictDomainModel):
    indicator_id: UUID
    dimension_id: UUID
    name: str = Field(min_length=1, max_length=200)


class InstrumentDimension(StrictDomainModel):
    dimension_id: UUID
    variable_id: UUID
    name: str = Field(min_length=1, max_length=200)


class InstrumentVariable(StrictDomainModel):
    variable_id: UUID
    name: str = Field(min_length=1, max_length=200)
    scale: Literal["nominal", "ordinal", "interval", "ratio", "unknown"] = "unknown"
    methodology_variable_id: UUID | None = None


class ScoringRule(StrictDomainModel):
    scoring_rule_id: UUID
    scope: Literal["dimension", "instrument"]
    dimension_id: UUID | None = None
    item_ids: list[UUID] = Field(min_length=1)
    aggregation: Literal["sum", "mean"]
    missing_policy: Literal["all_required"] = "all_required"
    confirmed: bool = False

    @model_validator(mode="after")
    def validate_scope_coherence(self) -> ScoringRule:
        if self.scope == "dimension":
            if self.dimension_id is None:
                raise ValueError("Una regla de ámbito 'dimension' requiere declarar dimension_id.")
        elif self.scope == "instrument":
            if self.dimension_id is not None:
                raise ValueError("Una regla de ámbito 'instrument' no debe declarar dimension_id.")
        return self


class InstrumentProvenance(StrictDomainModel):
    source_kind: Literal["document", "manual"]
    source_document_id: UUID | None = None
    source_document_hash: Sha256Hex | None = None
    methodology_review_id: UUID
    methodology_review_version: int = Field(ge=0)
    methodology_review_hash: Sha256Hex

    @model_validator(mode="after")
    def validate_provenance_coherence(self) -> InstrumentProvenance:
        if self.source_kind == "document":
            if self.source_document_id is None or self.source_document_hash is None:
                raise ValueError(
                    "La procedencia de tipo 'document' requiere source_document_id y "
                    "source_document_hash."
                )
        elif self.source_kind == "manual":
            if self.source_document_id is not None or self.source_document_hash is not None:
                raise ValueError(
                    "La procedencia de tipo 'manual' no debe declarar documento fuente."
                )
        return self


class InstrumentConfirmation(StrictDomainModel):
    state: Literal["pending", "confirmed"] = "pending"
    confirmed_at: datetime | None = None
    confirmer_ref: str | None = Field(default=None, min_length=1, max_length=200)

    @model_validator(mode="after")
    def validate_confirmation(self) -> InstrumentConfirmation:
        if self.state == "confirmed":
            if self.confirmed_at is None:
                raise ValueError("La confirmación humana requiere una marca temporal confirmed_at.")
            if not self.confirmer_ref or not self.confirmer_ref.strip():
                raise ValueError(
                    "La confirmación humana requiere una referencia de auditor confirmer_ref."
                )
        elif self.state == "pending":
            if self.confirmed_at is not None or self.confirmer_ref is not None:
                raise ValueError(
                    "Una confirmación 'pending' no debe contener confirmed_at ni confirmer_ref."
                )
        return self


class ItemColumnMapping(StrictDomainModel):
    item_id: UUID
    column_name: str = Field(min_length=1, max_length=128)

    @model_validator(mode="after")
    def validate_column_privacy(self) -> ItemColumnMapping:
        if is_pii_column(self.column_name):
            raise ValueError(
                f"La columna '{self.column_name}' contiene un identificador personal o PII y "
                "no puede mapearse."
            )
        return self


class DatasetMapping(StrictDomainModel):
    dataset_id: UUID
    dataset_hash: Sha256Hex
    instrument_version: int = Field(ge=0)
    item_columns: list[ItemColumnMapping] = Field(default_factory=list)
    status: Literal["draft", "confirmed", "stale"] = "draft"
    confirmation: InstrumentConfirmation = Field(default_factory=InstrumentConfirmation)

    @model_validator(mode="after")
    def validate_mapping_rules(self) -> DatasetMapping:
        item_ids = [m.item_id for m in self.item_columns]
        if len(set(item_ids)) != len(item_ids):
            raise ValueError("No se permite mapear el mismo ítem más de una vez en item_columns.")

        columns = [m.column_name.strip() for m in self.item_columns]
        if len(set(columns)) != len(columns):
            raise ValueError(
                "No se permite vincular una columna con varios ítems (correspondencia 1 a 1)."
            )

        if self.status == "confirmed":
            if self.confirmation.state != "confirmed":
                raise ValueError(
                    "El mapeo no puede tener status 'confirmed' sin confirmation.state='confirmed'."
                )
        elif self.status == "draft":
            if self.confirmation.state == "confirmed":
                raise ValueError("Un mapeo en status 'draft' no puede estar confirmado.")

        return self


class InstrumentContext(StrictDomainModel):
    schema_version: Literal["1.0.0"] = "1.0.0"
    instrument_id: UUID
    project_id: UUID
    research_package_id: UUID | None = None
    version: int = Field(default=0, ge=0)
    status: Literal["draft", "reviewed", "stale"] = "draft"
    created_at: datetime
    updated_at: datetime
    provenance: InstrumentProvenance | None = None
    confirmation: InstrumentConfirmation = Field(default_factory=InstrumentConfirmation)
    variables: list[InstrumentVariable] = Field(min_length=1)
    dimensions: list[InstrumentDimension] = Field(min_length=1)
    indicators: list[InstrumentIndicator] = Field(min_length=1)
    items: list[InstrumentItem] = Field(min_length=1)
    scoring_rules: list[ScoringRule] = Field(default_factory=list)
    dataset_mapping: DatasetMapping | None = None

    @model_validator(mode="after")
    def validate_academic_integrity(self) -> InstrumentContext:
        # 1. Unicidad de identificadores
        var_ids = [v.variable_id for v in self.variables]
        dim_ids = [d.dimension_id for d in self.dimensions]
        ind_ids = [i.indicator_id for i in self.indicators]
        item_ids = [it.item_id for it in self.items]
        scoring_ids = [s.scoring_rule_id for s in self.scoring_rules]

        if len(set(var_ids)) != len(var_ids):
            raise ValueError("Los identificadores de variables deben ser únicos.")
        if len(set(dim_ids)) != len(dim_ids):
            raise ValueError("Los identificadores de dimensiones deben ser únicos.")
        if len(set(ind_ids)) != len(ind_ids):
            raise ValueError("Los identificadores de indicadores deben ser únicos.")
        if len(set(item_ids)) != len(item_ids):
            raise ValueError("Los identificadores de ítems deben ser únicos.")
        if len(set(scoring_ids)) != len(scoring_ids):
            raise ValueError("Los identificadores de reglas de puntuación deben ser únicos.")

        all_ids = var_ids + dim_ids + ind_ids + item_ids + scoring_ids + [self.instrument_id]
        if len(set(all_ids)) != len(all_ids):
            raise ValueError(
                "Los identificadores de todas las entidades deben ser globalmente únicos."
            )

        # 2. Coherencia jerárquica estricta:
        # Dimensión -> Variable
        var_set = set(var_ids)
        for dim in self.dimensions:
            if dim.variable_id not in var_set:
                raise ValueError(
                    f"La dimensión '{dim.name}' ({dim.dimension_id}) referencia una variable "
                    "inexistente."
                )

        # Indicador -> Dimensión
        dim_map = {d.dimension_id: d for d in self.dimensions}
        for ind in self.indicators:
            if ind.dimension_id not in dim_map:
                raise ValueError(
                    f"El indicador '{ind.name}' ({ind.indicator_id}) referencia una dimensión "
                    "inexistente."
                )

        # Ítem -> Variable, Dimensión, Indicador
        ind_map = {i.indicator_id: i for i in self.indicators}
        item_map = {it.item_id: it for it in self.items}
        for item in self.items:
            if item.variable_id not in var_set:
                raise ValueError(
                    f"El ítem '{item.item_id}' referencia una variable inexistente "
                    f"({item.variable_id})."
                )
            if item.dimension_id not in dim_map:
                raise ValueError(f"El ítem '{item.item_id}' referencia una dimensión inexistente.")
            if item.indicator_id not in ind_map:
                raise ValueError(f"El ítem '{item.item_id}' referencia un indicador inexistente.")

            # Validar pertenencia dimensional cruzada
            dim = dim_map[item.dimension_id]
            if dim.variable_id != item.variable_id:
                raise ValueError(
                    f"Inconsistencia jerárquica en el ítem '{item.item_id}': dimensión "
                    f"{dim.dimension_id} pertenece a variable {dim.variable_id}, no a "
                    f"{item.variable_id}."
                )

            ind = ind_map[item.indicator_id]
            if ind.dimension_id != item.dimension_id:
                raise ValueError(
                    f"Inconsistencia jerárquica en el ítem '{item.item_id}': indicador "
                    f"{ind.indicator_id} pertenece a dimensión {ind.dimension_id}, no a "
                    f"{item.dimension_id}."
                )

        # 3. Coherencia de reglas de puntuación
        item_set = set(item_ids)
        for rule in self.scoring_rules:
            # Validar existencia de cada item_id en la regla
            rule_item_set = set(rule.item_ids)
            invalid_items = rule_item_set - item_set
            if invalid_items:
                raise ValueError(
                    f"La regla '{rule.scoring_rule_id}' referencia ítems inexistentes: "
                    f"{invalid_items}."
                )

            if rule.scope == "dimension":
                if rule.dimension_id not in dim_map:
                    raise ValueError(
                        f"La regla '{rule.scoring_rule_id}' apunta a una dimensión inexistente "
                        f"({rule.dimension_id})."
                    )
                # Todos los ítems de la regla deben pertenecer a esa dimensión
                for i_id in rule.item_ids:
                    if item_map[i_id].dimension_id != rule.dimension_id:
                        raise ValueError(
                            f"La regla de dimensión '{rule.scoring_rule_id}' incluye el ítem "
                            f"'{i_id}' que pertenece a otra dimensión "
                            f"({item_map[i_id].dimension_id})."
                        )
            elif rule.scope == "instrument":
                if rule.dimension_id is not None:
                    raise ValueError(
                        f"La regla de instrumento '{rule.scoring_rule_id}' no debe declarar "
                        "dimension_id."
                    )

        # En estado 'reviewed', requiere procedencia metodológica, confirmación y reglas
        if self.status == "reviewed":
            if self.provenance is None:
                raise ValueError(
                    "Un instrumento en estado 'reviewed' requiere declarar obligatoriamente "
                    "'provenance' con su referencia metodológica confirmada."
                )
            if self.confirmation.state != "confirmed":
                raise ValueError(
                    "Un instrumento en estado 'reviewed' requiere confirmation.state='confirmed'."
                )
            unconfirmed = [str(r.scoring_rule_id) for r in self.scoring_rules if not r.confirmed]
            if unconfirmed:
                raise ValueError(
                    "Un instrumento revisado requiere que todas sus reglas "
                    f"de puntuación estén confirmadas. Reglas pendientes: {', '.join(unconfirmed)}."
                )

        # Coherencia entre status draft y confirmación
        if self.status == "draft" and self.confirmation.state == "confirmed":
            raise ValueError("Un instrumento confirmado no puede permanecer en estado 'draft'.")

        # 4. Coherencia de marcas temporales
        if self.created_at > self.updated_at:
            raise ValueError("created_at no puede ser posterior a updated_at.")
        if self.confirmation.confirmed_at is not None:
            if self.confirmation.confirmed_at < self.created_at:
                raise ValueError(
                    "confirmed_at no puede ser anterior a la creación del instrumento."
                )

        # 5. Coherencia del mapeo con el dataset
        if self.dataset_mapping is not None:
            if self.dataset_mapping.instrument_version != self.version:
                raise ValueError(
                    f"La versión del instrumento en dataset_mapping "
                    f"({self.dataset_mapping.instrument_version}) no coincide con la versión "
                    f"actual del instrumento ({self.version})."
                )

            mapped_items = {m.item_id for m in self.dataset_mapping.item_columns}

            # Todos los ítems mapeados deben existir en el instrumento
            invalid_mapped = mapped_items - item_set
            if invalid_mapped:
                raise ValueError(
                    "dataset_mapping contiene identificadores de ítems que no pertenecen "
                    f"al instrumento: {invalid_mapped}."
                )

            # Si el mapeo está confirmado, debe cubrir el 100% de los ítems
            if self.dataset_mapping.status == "confirmed":
                missing_items = item_set - mapped_items
                if missing_items:
                    raise ValueError(
                        f"Un mapeo confirmado debe cubrir todos los ítems del instrumento. "
                        f"Ítems sin mapear: {len(missing_items)}."
                    )

        return self
