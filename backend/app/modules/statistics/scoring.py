"""Pure, deterministic scoring helpers for confirmed instrument rules.

The module deliberately receives explicit item specifications and row mappings.
It has no dependency on Research persistence, HTTP, authorization, or the
InstrumentContext reader; those concerns will be composed after Research 18A.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Final, Literal

from .inferential import TechniqueResult, cronbach_alpha

SCORING_ENGINE_VERSION: Final = "1.0.0"


class ScoringValidationError(ValueError):
    """Raised for an explicit coding, range, or scoring-rule violation."""

    def __init__(self, row_index: int, item_id: str, reason: str) -> None:
        super().__init__(f"Fila {row_index}, ítem {item_id}: {reason}.")
        self.row_index = row_index
        self.item_id = item_id
        self.reason = reason


@dataclass(frozen=True)
class ItemScoringSpec:
    """Confirmed coding metadata for one input column, independent of Research DTOs."""

    item_id: str
    column_name: str
    response_type: Literal["single_choice", "numeric"]
    response_options: tuple[tuple[str, float], ...] = ()
    valid_min: float | None = None
    valid_max: float | None = None
    reverse_scored: bool = False
    reverse_rule: Literal["min_plus_max_minus_value"] | None = None

    def __post_init__(self) -> None:
        if not self.item_id or not self.column_name:
            raise ValueError("El ítem y la columna deben estar identificados.")
        if (self.valid_min is None) != (self.valid_max is None):
            raise ValueError("El rango válido requiere mínimo y máximo.")
        if self.valid_min is not None and self.valid_min >= self.valid_max:
            raise ValueError("El mínimo válido debe ser menor que el máximo.")
        option_codes = [code for code, _ in self.response_options]
        if len(set(option_codes)) != len(option_codes):
            raise ValueError("Los códigos de respuesta deben ser únicos.")
        if self.response_type == "single_choice" and len(self.response_options) < 2:
            raise ValueError("Un ítem de opción única requiere al menos dos opciones.")
        if self.response_type == "numeric" and self.response_options:
            raise ValueError("Un ítem numérico no admite opciones codificadas.")
        for _, numeric_value in self.response_options:
            if not math.isfinite(numeric_value):
                raise ValueError("Los valores codificados deben ser finitos.")
            if self.valid_min is not None and not self.valid_min <= numeric_value <= self.valid_max:
                raise ValueError("Los valores codificados deben respetar el rango válido.")
        if self.reverse_scored:
            if self.reverse_rule != "min_plus_max_minus_value":
                raise ValueError("La inversión requiere una regla explícita.")
            if self.valid_min is None or self.valid_max is None:
                raise ValueError("La inversión requiere extremos de escala confirmados.")
        elif self.reverse_rule is not None:
            raise ValueError("La regla de inversión solo corresponde a ítems invertidos.")


@dataclass(frozen=True)
class ScoringRuleSpec:
    """Confirmed aggregation metadata for one dimension or full instrument."""

    rule_id: str
    item_ids: tuple[str, ...]
    aggregation: Literal["sum", "mean"]
    missing_policy: Literal["all_required"]

    def __post_init__(self) -> None:
        if not self.rule_id or not self.item_ids:
            raise ValueError("La regla requiere identificador e ítems.")
        if len(set(self.item_ids)) != len(self.item_ids):
            raise ValueError("Los ítems de una regla deben ser únicos.")


@dataclass(frozen=True)
class ScoringComputation:
    """Derived scores and accounting for absent values, without mutating source rows."""

    values: tuple[float | None, ...]
    valid_rows: int
    missing_rows: int


@dataclass(frozen=True)
class ReliabilityComputation:
    """Cronbach result plus complete-case accounting for the original recoded items."""

    result: TechniqueResult
    valid_rows: int
    excluded_rows: int


def _ensure_unique_specs(item_specs: Sequence[ItemScoringSpec]) -> None:
    item_ids = [spec.item_id for spec in item_specs]
    columns = [spec.column_name for spec in item_specs]
    if len(set(item_ids)) != len(item_ids):
        raise ValueError("Los identificadores de ítem deben ser únicos.")
    if len(set(columns)) != len(columns):
        raise ValueError("Una columna no puede representar dos ítems.")


def _recode_value(spec: ItemScoringSpec, value: object, row_index: int) -> float | None:
    if value is None:
        return None
    if spec.response_type == "single_choice":
        options = dict(spec.response_options)
        code = str(value)
        if code not in options:
            raise ScoringValidationError(row_index, spec.item_id, "código de respuesta desconocido")
        result = options[code]
    else:
        if isinstance(value, bool):
            raise ScoringValidationError(row_index, spec.item_id, "respuesta numérica inválida")
        try:
            result = float(value)
        except (TypeError, ValueError) as error:
            raise ScoringValidationError(
                row_index, spec.item_id, "respuesta numérica inválida"
            ) from error
        if not math.isfinite(result):
            raise ScoringValidationError(row_index, spec.item_id, "respuesta numérica no finita")
    if spec.valid_min is not None and not spec.valid_min <= result <= spec.valid_max:
        raise ScoringValidationError(row_index, spec.item_id, "valor fuera del rango confirmado")
    if spec.reverse_scored:
        assert spec.valid_min is not None and spec.valid_max is not None
        result = spec.valid_min + spec.valid_max - result
    return result


def recode_rows(
    rows: Sequence[Mapping[str, object]], item_specs: Sequence[ItemScoringSpec]
) -> tuple[tuple[float | None, ...], ...]:
    """Return recoded original item values, preserving one tuple per input row."""

    _ensure_unique_specs(item_specs)
    recoded_rows: list[tuple[float | None, ...]] = []
    for row_index, row in enumerate(rows):
        values: list[float | None] = []
        for spec in item_specs:
            if spec.column_name not in row:
                raise ScoringValidationError(row_index, spec.item_id, "columna vinculada ausente")
            values.append(_recode_value(spec, row[spec.column_name], row_index))
        recoded_rows.append(tuple(values))
    return tuple(recoded_rows)


def calculate_scores(
    rows: Sequence[Mapping[str, object]],
    item_specs: Sequence[ItemScoringSpec],
    rule: ScoringRuleSpec,
) -> ScoringComputation:
    """Calculate confirmed sum or mean scores with the all-required policy."""

    _ensure_unique_specs(item_specs)
    spec_by_item = {spec.item_id: spec for spec in item_specs}
    if set(rule.item_ids) != set(spec_by_item):
        raise ValueError("La regla debe recibir exactamente los ítems especificados.")
    ordered_specs = tuple(spec_by_item[item_id] for item_id in rule.item_ids)
    recoded = recode_rows(rows, ordered_specs)
    values: list[float | None] = []
    missing_rows = 0
    for row in recoded:
        if any(value is None for value in row):
            values.append(None)
            missing_rows += 1
            continue
        complete = tuple(float(value) for value in row)
        values.append(sum(complete) if rule.aggregation == "sum" else sum(complete) / len(complete))
    return ScoringComputation(
        values=tuple(values), valid_rows=len(rows) - missing_rows, missing_rows=missing_rows
    )


def calculate_cronbach_reliability(
    rows: Sequence[Mapping[str, object]], item_specs: Sequence[ItemScoringSpec]
) -> ReliabilityComputation:
    """Reuse the existing alpha over complete rows of original recoded items only."""

    recoded = recode_rows(rows, item_specs)
    complete_rows = tuple(
        tuple(float(value) for value in row)
        for row in recoded
        if all(value is not None for value in row)
    )
    return ReliabilityComputation(
        result=cronbach_alpha(complete_rows),
        valid_rows=len(complete_rows),
        excluded_rows=len(recoded) - len(complete_rows),
    )
