"""Deterministic parametric two-sample comparison techniques."""

from __future__ import annotations

import math
from collections.abc import Sequence

from .distributions import student_t_critical_two_sided, student_t_two_sided
from .inferential import (
    StatisticalCalculationError,
    TechniqueResult,
    _number,
    _paired_numbers,
    _sample_variance,
)


def _group(values: Sequence[object]) -> list[float]:
    result = []
    for value in values:
        parsed = _number(value)
        if parsed is not None:
            result.append(parsed)
    if len(result) < 2:
        raise StatisticalCalculationError("Cada grupo requiere al menos dos valores válidos.")
    return result


def _t_statistic(mean_difference: float, standard_error: float) -> float:
    if standard_error == 0:
        if mean_difference == 0:
            return 0.0
        raise StatisticalCalculationError("La diferencia no tiene error estándar definido.")
    return mean_difference / standard_error


def _cohens_d(mean_difference: float, pooled_variance: float) -> float:
    if pooled_variance == 0:
        return 0.0
    return mean_difference / math.sqrt(pooled_variance)


def _mean_difference_interval(
    mean_difference: float, standard_error: float, degrees_of_freedom: float
) -> tuple[float, float]:
    critical = student_t_critical_two_sided(0.05, degrees_of_freedom)
    margin = critical * standard_error
    return mean_difference - margin, mean_difference + margin


def t_independent(left: Sequence[object], right: Sequence[object]) -> TechniqueResult:
    """Student's independent two-sample t test with pooled variance."""

    x = _group(left)
    y = _group(right)
    variance_x = _sample_variance(x)
    variance_y = _sample_variance(y)
    degrees_of_freedom = len(x) + len(y) - 2
    pooled = ((len(x) - 1) * variance_x + (len(y) - 1) * variance_y) / degrees_of_freedom
    mean_difference = sum(x) / len(x) - sum(y) / len(y)
    standard_error = math.sqrt(pooled * (1 / len(x) + 1 / len(y)))
    statistic = _t_statistic(mean_difference, standard_error)
    ci_low, ci_high = _mean_difference_interval(mean_difference, standard_error, degrees_of_freedom)
    return TechniqueResult(
        "t_independent",
        {
            "n_left": float(len(x)),
            "n_right": float(len(y)),
            "mean_difference": mean_difference,
            "t_statistic": statistic,
            "degrees_of_freedom": float(degrees_of_freedom),
            "p_value": student_t_two_sided(statistic, float(degrees_of_freedom)),
            "cohens_d": _cohens_d(mean_difference, pooled),
            "mean_difference_ci_95_low": ci_low,
            "mean_difference_ci_95_high": ci_high,
        },
    )


def t_welch(left: Sequence[object], right: Sequence[object]) -> TechniqueResult:
    """Welch's independent two-sample t test without equal-variance assumption."""

    x = _group(left)
    y = _group(right)
    variance_x = _sample_variance(x)
    variance_y = _sample_variance(y)
    left_component = variance_x / len(x)
    right_component = variance_y / len(y)
    standard_error = math.sqrt(left_component + right_component)
    denominator = (left_component**2 / (len(x) - 1)) + (right_component**2 / (len(y) - 1))
    if denominator == 0:
        degrees_of_freedom = float(len(x) + len(y) - 2)
    else:
        degrees_of_freedom = (left_component + right_component) ** 2 / denominator
    mean_difference = sum(x) / len(x) - sum(y) / len(y)
    statistic = _t_statistic(mean_difference, standard_error)
    ci_low, ci_high = _mean_difference_interval(mean_difference, standard_error, degrees_of_freedom)
    pooled = ((len(x) - 1) * variance_x + (len(y) - 1) * variance_y) / (len(x) + len(y) - 2)
    return TechniqueResult(
        "t_welch",
        {
            "n_left": float(len(x)),
            "n_right": float(len(y)),
            "mean_difference": mean_difference,
            "t_statistic": statistic,
            "degrees_of_freedom": degrees_of_freedom,
            "p_value": student_t_two_sided(statistic, degrees_of_freedom),
            "cohens_d": _cohens_d(mean_difference, pooled),
            "mean_difference_ci_95_low": ci_low,
            "mean_difference_ci_95_high": ci_high,
        },
    )


def t_paired(left: Sequence[object], right: Sequence[object]) -> TechniqueResult:
    """Paired Student's t test over complete matched pairs."""

    x, y = _paired_numbers(left, right)
    differences = [left_value - right_value for left_value, right_value in zip(x, y, strict=True)]
    if len(differences) < 2:
        raise StatisticalCalculationError("La prueba pareada requiere al menos dos pares válidos.")
    mean_difference = sum(differences) / len(differences)
    standard_error = math.sqrt(_sample_variance(differences) / len(differences))
    degrees_of_freedom = len(differences) - 1
    statistic = _t_statistic(mean_difference, standard_error)
    ci_low, ci_high = _mean_difference_interval(mean_difference, standard_error, degrees_of_freedom)
    return TechniqueResult(
        "t_paired",
        {
            "n": float(len(differences)),
            "mean_difference": mean_difference,
            "t_statistic": statistic,
            "degrees_of_freedom": float(degrees_of_freedom),
            "p_value": student_t_two_sided(statistic, float(degrees_of_freedom)),
            "cohens_dz": _cohens_d(mean_difference, _sample_variance(differences)),
            "mean_difference_ci_95_low": ci_low,
            "mean_difference_ci_95_high": ci_high,
        },
    )
