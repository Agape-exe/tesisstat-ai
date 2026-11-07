"""Domain models for research measurement instruments and psychometric scales."""

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
    def validate_item_coherence(self) -> "InstrumentItem":
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
    def validate_scope_coherence(self) -> "ScoringRule":
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
    def validate_provenance_coherence(self) -> "InstrumentProvenance":
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
    def validate_confirmation(self) -> "InstrumentConfirmation":
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
    def validate_column_privacy(self) -> "ItemColumnMapping":
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
    def validate_mapping_rules(self) -> "DatasetMapping":
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
