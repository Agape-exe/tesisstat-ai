"""Deterministic diagnostics used to report statistical assumptions."""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

from .inferential import _number


@dataclass(frozen=True)
class AssumptionDiagnostic:
    name: str
    status: str
    statistic: float | None
    p_value: float | None
    details: str


def _values(values: Sequence[object]) -> list[float]:
    parsed = []
    for value in values:
        number = _number(value)
        if number is not None:
            parsed.append(number)
    return parsed


def _beta_continued_fraction(a: float, b: float, x: float) -> float:
    factor = math.exp(math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b))
    factor *= x**a * (1 - x) ** b / a
    c = 1.0
    d = 1.0 - (a + b) * x / (a + 1)
    d = 1e-30 if abs(d) < 1e-30 else d
    d = 1 / d
    h = d
    for index in range(1, 201):
        even = 2 * index
        numerator = index * (b - index) * x / ((a + even - 1) * (a + even))
        d = 1 + numerator * d
        d = 1e-30 if abs(d) < 1e-30 else d
        c = 1 + numerator / c
        c = 1e-30 if abs(c) < 1e-30 else c
        d = 1 / d
        h *= d * c
        numerator = -(a + index) * (a + b + index) * x / ((a + even) * (a + even + 1))
        d = 1 + numerator * d
        d = 1e-30 if abs(d) < 1e-30 else d
        c = 1 + numerator / c
        c = 1e-30 if abs(c) < 1e-30 else c
        d = 1 / d
        delta = d * c
        h *= delta
        if abs(delta - 1) < 3e-14:
            break
    return factor * h


def _regularized_beta(a: float, b: float, x: float) -> float:
    if x <= 0:
        return 0.0
    if x >= 1:
        return 1.0
    if x < (a + 1) / (a + b + 2):
        return _beta_continued_fraction(a, b, x)
    return 1 - _beta_continued_fraction(b, a, 1 - x)


def _f_survival(statistic: float, df_one: float, df_two: float) -> float:
    if statistic <= 0:
        return 1.0
    x = (df_one * statistic) / (df_one * statistic + df_two)
    return max(0.0, min(1.0, 1 - _regularized_beta(df_one / 2, df_two / 2, x)))


def normality(values: Sequence[object], name: str = "normality") -> AssumptionDiagnostic:
    """Use Jarque–Bera with its chi-square(2) survival probability."""

    numbers = _values(values)
    if len(numbers) < 8:
        return AssumptionDiagnostic(
            name, "not_checked", None, None, "Se requieren al menos ocho valores numéricos."
        )
    mean = sum(numbers) / len(numbers)
    centered = [value - mean for value in numbers]
    second = sum(value**2 for value in centered) / len(numbers)
    if second == 0:
        return AssumptionDiagnostic(
            name, "not_checked", None, None, "La columna es constante; normalidad no es evaluable."
        )
    skew = sum(value**3 for value in centered) / len(numbers) / second**1.5
    kurtosis = sum(value**4 for value in centered) / len(numbers) / second**2
    statistic = len(numbers) / 6 * (skew**2 + (kurtosis - 3) ** 2 / 4)
    p_value = math.exp(-statistic / 2)
    status = "passed" if p_value >= 0.05 else "failed"
    return AssumptionDiagnostic(
        name,
        status,
        statistic,
        p_value,
        f"Jarque–Bera={statistic:.4g}; p aproximado={p_value:.4g}; alfa=0.05.",
    )


def homogeneity(
    groups: Sequence[Sequence[object]], name: str = "homogeneity"
) -> AssumptionDiagnostic:
    """Use the Brown–Forsythe/Levene F statistic on absolute median deviations."""

    parsed = [_values(group) for group in groups]
    if len(parsed) < 2 or any(len(group) < 2 for group in parsed):
        return AssumptionDiagnostic(
            name, "not_checked", None, None, "Cada grupo requiere al menos dos valores numéricos."
        )
    deviations = []
    for group in parsed:
        ordered = sorted(group)
        midpoint = len(ordered) // 2
        median = (
            ordered[midpoint]
            if len(ordered) % 2
            else (ordered[midpoint - 1] + ordered[midpoint]) / 2
        )
        deviations.append([abs(value - median) for value in group])
    all_deviations = [value for group in deviations for value in group]
    means = [sum(group) / len(group) for group in deviations]
    grand_mean = sum(all_deviations) / len(all_deviations)
    between = sum(
        len(group) * (mean - grand_mean) ** 2 for group, mean in zip(deviations, means, strict=True)
    )
    within = sum(
        sum((value - mean) ** 2 for value in group)
        for group, mean in zip(deviations, means, strict=True)
    )
    df_one = len(parsed) - 1
    df_two = len(all_deviations) - len(parsed)
    if within == 0:
        statistic = 0.0 if between == 0 else float("inf")
        p_value = 1.0 if between == 0 else 0.0
    else:
        statistic = (between / df_one) / (within / df_two)
        p_value = _f_survival(statistic, float(df_one), float(df_two))
    status = "passed" if p_value >= 0.05 else "failed"
    return AssumptionDiagnostic(
        name,
        status,
        statistic,
        p_value,
        f"Brown–Forsythe F={statistic:.4g}; p aproximado={p_value:.4g}; alfa=0.05.",
    )


def homoscedasticity(
    fitted: Sequence[object], residuals: Sequence[object], name: str = "homoscedasticity"
) -> AssumptionDiagnostic:
    """Use a Breusch–Pagan-style LM screening on squared residuals."""

    x = _values(fitted)
    errors = _values(residuals)
    if len(x) != len(errors) or len(x) < 5:
        return AssumptionDiagnostic(
            name, "not_checked", None, None, "Se requieren al menos cinco pares completos."
        )
    mean_x = sum(x) / len(x)
    centered_x = [value - mean_x for value in x]
    denominator = sum(value**2 for value in centered_x)
    if denominator == 0:
        return AssumptionDiagnostic(
            name, "not_checked", None, None, "Los valores ajustados son constantes."
        )
    squared = [error**2 for error in errors]
    mean_squared = sum(squared) / len(squared)
    slope = (
        sum(a * (b - mean_squared) for a, b in zip(centered_x, squared, strict=True)) / denominator
    )
    intercept = mean_squared - slope * mean_x
    predicted = [intercept + slope * value for value in x]
    total = sum((value - mean_squared) ** 2 for value in squared)
    if total == 0:
        return AssumptionDiagnostic(name, "passed", 0.0, 1.0, "Los residuos son constantes.")
    r_squared = (
        1
        - sum((actual - estimate) ** 2 for actual, estimate in zip(squared, predicted, strict=True))
        / total
    )
    statistic = len(x) * max(0.0, r_squared)
    p_value = math.exp(-statistic / 2)
    status = "passed" if p_value >= 0.05 else "failed"
    return AssumptionDiagnostic(
        name,
        status,
        statistic,
        p_value,
        f"LM={statistic:.4g}; p aproximado={p_value:.4g}; alfa=0.05.",
    )


def independence(name: str = "independence") -> AssumptionDiagnostic:
    """Report the design-dependent assumption without guessing from row order."""

    return AssumptionDiagnostic(
        name,
        "not_checked",
        None,
        None,
        "La independencia requiere confirmación del diseño y del procedimiento de muestreo.",
    )
