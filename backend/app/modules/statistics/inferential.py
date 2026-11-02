"""Small deterministic implementations for the first inferential techniques.

The functions in this module operate on already selected columns. They return
metrics only; selecting a technique remains the planner's responsibility and no
function evaluates code or dynamically imports a named technique.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

from .descriptive import is_missing
from .distributions import chi_square_survival, student_t_two_sided


class StatisticalCalculationError(ValueError):
    """Raised when a technique's data requirements are not satisfied."""


@dataclass(frozen=True)
class TechniqueResult:
    technique: str
    metrics: dict[str, float]
    warnings: tuple[str, ...] = ()


def _number(value: object) -> float | None:
    if value is None or (isinstance(value, str) and is_missing(value)):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError) as error:
        raise StatisticalCalculationError(f"Valor no numérico: {value!r}") from error
    if not math.isfinite(number):
        raise StatisticalCalculationError("Los valores numéricos deben ser finitos.")
    return number


def _paired_numbers(
    left: Sequence[object], right: Sequence[object]
) -> tuple[list[float], list[float]]:
    if len(left) != len(right):
        raise StatisticalCalculationError("Las columnas deben tener la misma cantidad de filas.")
    pairs = [
        (left_value, right_value)
        for left_value, right_value in zip(left, right, strict=True)
        if _number(left_value) is not None and _number(right_value) is not None
    ]
    if not pairs:
        raise StatisticalCalculationError("No hay pares numéricos válidos.")
    return [float(_number(pair[0])) for pair in pairs], [float(_number(pair[1])) for pair in pairs]


def _pearson(left: Sequence[float], right: Sequence[float]) -> float:
    left_mean = sum(left) / len(left)
    right_mean = sum(right) / len(right)
    centered_left = [value - left_mean for value in left]
    centered_right = [value - right_mean for value in right]
    numerator = sum(a * b for a, b in zip(centered_left, centered_right, strict=True))
    left_sum = sum(value * value for value in centered_left)
    right_sum = sum(value * value for value in centered_right)
    denominator = math.sqrt(left_sum * right_sum)
    if denominator == 0:
        raise StatisticalCalculationError(
            "La correlación no está definida para una columna constante."
        )
    return numerator / denominator


def pearson(left: Sequence[object], right: Sequence[object]) -> TechniqueResult:
    """Calculate Pearson's r over complete finite pairs."""

    x, y = _paired_numbers(left, right)
    if len(x) < 3:
        raise StatisticalCalculationError("Pearson requiere al menos tres pares válidos.")
    correlation = _pearson(x, y)
    degrees_of_freedom = len(x) - 2
    statistic = (
        math.copysign(float.fromhex("0x1.fffffffffffffp+1023"), correlation)
        if abs(correlation) == 1
        else correlation * math.sqrt(degrees_of_freedom / (1 - correlation**2))
    )
    return TechniqueResult(
        "pearson",
        {
            "n": float(len(x)),
            "r": correlation,
            "t_statistic": statistic,
            "degrees_of_freedom": float(degrees_of_freedom),
            "p_value": 0.0
            if abs(correlation) == 1
            else student_t_two_sided(statistic, float(degrees_of_freedom)),
        },
    )


def _ranks(values: Sequence[float]) -> list[float]:
    ordered = sorted(enumerate(values), key=lambda item: item[1])
    result = [0.0] * len(values)
    index = 0
    while index < len(ordered):
        end = index + 1
        while end < len(ordered) and ordered[end][1] == ordered[index][1]:
            end += 1
        rank = (index + 1 + end) / 2
        for position in range(index, end):
            result[ordered[position][0]] = rank
        index = end
    return result


def spearman(left: Sequence[object], right: Sequence[object]) -> TechniqueResult:
    """Calculate Spearman's rho using average ranks for ties."""

    x, y = _paired_numbers(left, right)
    if len(x) < 3:
        raise StatisticalCalculationError("Spearman requiere al menos tres pares válidos.")
    rho = _pearson(_ranks(x), _ranks(y))
    degrees_of_freedom = len(x) - 2
    statistic = (
        math.copysign(float.fromhex("0x1.fffffffffffffp+1023"), rho)
        if abs(rho) == 1
        else rho * math.sqrt(degrees_of_freedom / (1 - rho**2))
    )
    return TechniqueResult(
        "spearman",
        {
            "n": float(len(x)),
            "rho": rho,
            "t_statistic": statistic,
            "degrees_of_freedom": float(degrees_of_freedom),
            "p_value": 0.0
            if abs(rho) == 1
            else student_t_two_sided(statistic, float(degrees_of_freedom)),
        },
        ("El p-valor de Spearman usa la aproximación t; úsalo con cautela en muestras pequeñas.",),
    )


def _paired_categories(left: Sequence[object], right: Sequence[object]) -> list[tuple[str, str]]:
    if len(left) != len(right):
        raise StatisticalCalculationError("Las columnas deben tener la misma cantidad de filas.")
    pairs = [
        (str(left_value).strip(), str(right_value).strip())
        for left_value, right_value in zip(left, right, strict=True)
        if not is_missing(None if left_value is None else str(left_value))
        and not is_missing(None if right_value is None else str(right_value))
    ]
    if not pairs:
        raise StatisticalCalculationError("No hay pares categóricos válidos.")
    return pairs


def _contingency(pairs: Sequence[tuple[str, str]]) -> tuple[list[str], list[str], list[list[int]]]:
    rows = sorted({pair[0] for pair in pairs})
    columns = sorted({pair[1] for pair in pairs})
    table = [[0 for _ in columns] for _ in rows]
    row_index = {value: index for index, value in enumerate(rows)}
    column_index = {value: index for index, value in enumerate(columns)}
    for row, column in pairs:
        table[row_index[row]][column_index[column]] += 1
    return rows, columns, table


def chi_square(left: Sequence[object], right: Sequence[object]) -> TechniqueResult:
    """Calculate Pearson's chi-square statistic for independence."""

    pairs = _paired_categories(left, right)
    rows, columns, table = _contingency(pairs)
    if len(rows) < 2 or len(columns) < 2:
        raise StatisticalCalculationError(
            "Chi-cuadrado requiere al menos dos categorías por variable."
        )
    row_totals = [sum(row) for row in table]
    column_totals = [
        sum(table[row][column] for row in range(len(rows))) for column in range(len(columns))
    ]
    total = len(pairs)
    statistic = 0.0
    for row, row_total in enumerate(row_totals):
        for column, column_total in enumerate(column_totals):
            expected = row_total * column_total / total
            statistic += (table[row][column] - expected) ** 2 / expected
    degrees_of_freedom = (len(rows) - 1) * (len(columns) - 1)
    return TechniqueResult(
        "chi_square",
        {
            "n": float(total),
            "chi_square": statistic,
            "degrees_of_freedom": float(degrees_of_freedom),
            "p_value": chi_square_survival(statistic, float(degrees_of_freedom)),
        },
    )


def _log_combination(n: int, k: int) -> float:
    if k < 0 or k > n:
        return float("-inf")
    return math.lgamma(n + 1) - math.lgamma(k + 1) - math.lgamma(n - k + 1)


def fisher_exact(left: Sequence[object], right: Sequence[object]) -> TechniqueResult:
    """Calculate a two-sided Fisher exact p-value for a 2 × 2 table."""

    pairs = _paired_categories(left, right)
    rows, columns, table = _contingency(pairs)
    if len(rows) != 2 or len(columns) != 2:
        raise StatisticalCalculationError("Fisher exacto requiere una tabla 2 × 2.")
    a, b = table[0]
    c, d = table[1]
    row_one = a + b
    row_two = c + d
    column_one = a + c
    total = row_one + row_two
    lower = max(0, row_one - (total - column_one))
    upper = min(row_one, column_one)

    def probability(value: int) -> float:
        return math.exp(
            _log_combination(column_one, value)
            + _log_combination(total - column_one, row_one - value)
            - _log_combination(total, row_one)
        )

    observed = probability(a)
    p_value = sum(
        probability(value)
        for value in range(lower, upper + 1)
        if probability(value) <= observed + 1e-12
    )
    odds_ratio = float("inf") if b * c == 0 and a * d > 0 else (a * d) / (b * c) if b * c else 0.0
    return TechniqueResult(
        "fisher_exact",
        {"n": float(total), "odds_ratio": odds_ratio, "p_value": min(1.0, p_value)},
    )


def _sample_variance(values: Sequence[float]) -> float:
    if len(values) < 2:
        raise StatisticalCalculationError("Se requieren al menos dos observaciones completas.")
    mean = sum(values) / len(values)
    return sum((value - mean) ** 2 for value in values) / (len(values) - 1)


def cronbach_alpha(rows: Sequence[Sequence[object]]) -> TechniqueResult:
    """Calculate Cronbach's alpha using complete rows and sample variances."""

    if not rows or not rows[0] or len(rows[0]) < 2:
        raise StatisticalCalculationError("Alfa de Cronbach requiere al menos dos ítems.")
    width = len(rows[0])
    complete: list[list[float]] = []
    for row in rows:
        if len(row) != width:
            raise StatisticalCalculationError("Todos los registros deben tener los mismos ítems.")
        parsed = [_number(value) for value in row]
        if all(value is not None for value in parsed):
            complete.append([float(value) for value in parsed])
    if len(complete) < 2:
        raise StatisticalCalculationError("Alfa de Cronbach requiere al menos dos filas completas.")
    item_variances = [_sample_variance([row[index] for row in complete]) for index in range(width)]
    totals = [sum(row) for row in complete]
    total_variance = _sample_variance(totals)
    if total_variance == 0:
        raise StatisticalCalculationError("La varianza total es cero; alfa no está definido.")
    alpha = width / (width - 1) * (1 - sum(item_variances) / total_variance)
    return TechniqueResult(
        "cronbach_alpha",
        {"n": float(len(complete)), "items": float(width), "alpha": alpha},
    )
