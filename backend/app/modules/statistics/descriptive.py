"""Deterministic descriptive statistics for the synthetic CSV datasets.

Conventions: numeric columns contain only finite numeric values after missing values
are ignored; headers that look like identifiers are never numeric variables. Quantiles
use Hyndman--Fan type 7 (linear interpolation at ``1 + (n - 1) * p``), and variance
and standard deviation use the sample denominator ``n - 1``.
"""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass
from statistics import fmean
from typing import Literal

ColumnKind = Literal["numeric", "categorical", "identifier"]


@dataclass(frozen=True)
class ColumnProfile:
    name: str
    kind: ColumnKind
    valid_count: int
    missing_count: int


@dataclass(frozen=True)
class Frequency:
    value: str
    count: int
    percentage: float


@dataclass(frozen=True)
class NumericSummary:
    valid_count: int
    missing_count: int
    mean: float | None
    median: float | None
    modes: list[float]
    mode_tied: bool
    minimum: float | None
    maximum: float | None
    sample_standard_deviation: float | None
    sample_variance: float | None
    quantiles: dict[str, float] | None
    warnings: list[str]


@dataclass(frozen=True)
class CategoricalSummary:
    valid_count: int
    missing_count: int
    frequencies: list[Frequency]
    warnings: list[str]


@dataclass(frozen=True)
class DescriptiveResult:
    column: str
    kind: ColumnKind
    numeric: NumericSummary | None
    categorical: CategoricalSummary | None


_IDENTIFIER_TOKENS = ("id", "identifier", "code", "codigo", "cod")
_MISSING_VALUES = {"", "na", "n/a", "null", "none"}


def is_missing(value: str | None) -> bool:
    return value is None or value.strip().casefold() in _MISSING_VALUES


def is_identifier_name(name: str) -> bool:
    normalized = name.strip().casefold().replace("-", "_").replace(" ", "_")
    parts = tuple(part for part in normalized.split("_") if part)
    return any(part in _IDENTIFIER_TOKENS for part in parts)


def _as_number(value: str) -> float | None:
    try:
        parsed = float(value.strip())
    except ValueError:
        return None
    return parsed if math.isfinite(parsed) else None


def profile_column(name: str, values: list[str | None]) -> ColumnProfile:
    missing_count = sum(is_missing(value) for value in values)
    present = [value for value in values if not is_missing(value)]
    valid_count = len(present)
    if is_identifier_name(name):
        return ColumnProfile(name, "identifier", valid_count, missing_count)
    if present and all(_as_number(value or "") is not None for value in present):
        return ColumnProfile(name, "numeric", valid_count, missing_count)
    return ColumnProfile(name, "categorical", valid_count, missing_count)


def _quantile_type_7(sorted_values: list[float], probability: float) -> float:
    if len(sorted_values) == 1:
        return sorted_values[0]
    position = (len(sorted_values) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return sorted_values[lower]
    fraction = position - lower
    return sorted_values[lower] + fraction * (sorted_values[upper] - sorted_values[lower])


def describe_numeric(values: list[str | None]) -> NumericSummary:
    numbers = [_as_number(value or "") for value in values if not is_missing(value)]
    valid = [number for number in numbers if number is not None]
    missing_count = sum(is_missing(value) for value in values)
    warnings: list[str] = []
    if not valid:
        return NumericSummary(
            0,
            missing_count,
            None,
            None,
            [],
            False,
            None,
            None,
            None,
            None,
            None,
            ["No hay valores numéricos válidos para analizar."],
        )

    ordered = sorted(valid)
    counts = Counter(ordered)
    highest_frequency = max(counts.values())
    modes = sorted(value for value, count in counts.items() if count == highest_frequency)
    if highest_frequency == 1:
        modes = []
        warnings.append("No hay moda: todos los valores válidos son distintos.")
    elif len(modes) > 1:
        warnings.append("La moda tiene empate entre varios valores.")

    variance: float | None = None
    standard_deviation: float | None = None
    if len(ordered) < 2:
        warnings.append(
            "La varianza y desviación estándar muestrales requieren al menos dos valores."
        )
    else:
        mean = fmean(ordered)
        variance = sum((value - mean) ** 2 for value in ordered) / (len(ordered) - 1)
        standard_deviation = math.sqrt(variance)

    quantiles = {
        "p0": _quantile_type_7(ordered, 0),
        "p25": _quantile_type_7(ordered, 0.25),
        "p50": _quantile_type_7(ordered, 0.5),
        "p75": _quantile_type_7(ordered, 0.75),
        "p100": _quantile_type_7(ordered, 1),
    }
    return NumericSummary(
        valid_count=len(ordered),
        missing_count=missing_count,
        mean=fmean(ordered),
        median=quantiles["p50"],
        modes=modes,
        mode_tied=len(modes) > 1,
        minimum=ordered[0],
        maximum=ordered[-1],
        sample_standard_deviation=standard_deviation,
        sample_variance=variance,
        quantiles=quantiles,
        warnings=warnings,
    )


def describe_categorical(values: list[str | None]) -> CategoricalSummary:
    present = [
        value.strip() for value in values if not is_missing(value) for value in [value or ""]
    ]
    missing_count = len(values) - len(present)
    if not present:
        return CategoricalSummary(
            0, missing_count, [], ["No hay categorías válidas para analizar."]
        )
    counts = Counter(present)
    frequencies = [
        Frequency(value=value, count=count, percentage=(count / len(present)) * 100)
        for value, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    ]
    return CategoricalSummary(len(present), missing_count, frequencies, [])


def describe_column(name: str, values: list[str | None]) -> DescriptiveResult:
    profile = profile_column(name, values)
    if profile.kind == "numeric":
        return DescriptiveResult(name, profile.kind, describe_numeric(values), None)
    return DescriptiveResult(name, profile.kind, None, describe_categorical(values))
