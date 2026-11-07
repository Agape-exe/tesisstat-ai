"""Independent boundary contract for InstrumentContext v1.0.0.

Research owns the persistence and confirmation lifecycle of this contract.
Statistics consumes it via an authorized read-only protocol.
No shared contracts v1.0.0 (ResearchPackage, DatasetReference, etc.) are modified.
"""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field, model_validator

from app.modules.research.instrument.models import (
    DatasetMapping,
    InstrumentConfirmation,
    InstrumentDimension,
    InstrumentIndicator,
    InstrumentItem,
    InstrumentProvenance,
    InstrumentVariable,
    ScoringRule,
    StrictDomainModel,
)


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
    def validate_academic_integrity(self) -> "InstrumentContext":
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
