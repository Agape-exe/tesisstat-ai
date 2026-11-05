"""Deterministic multi-group and post-hoc comparison techniques."""

from __future__ import annotations

import math
from collections.abc import Sequence
from itertools import combinations

from .distributions import f_survival, student_t_two_sided
from .inferential import StatisticalCalculationError, TechniqueResult, _number, _sample_variance


def _groups(groups: Sequence[Sequence[object]]) -> list[list[float]]:
    if len(groups) < 3:
        raise StatisticalCalculationError("Se requieren al menos tres grupos.")
    parsed_groups: list[list[float]] = []
    for group in groups:
        parsed = [number for value in group if (number := _number(value)) is not None]
        if len(parsed) < 2:
            raise StatisticalCalculationError("Cada grupo requiere al menos dos valores válidos.")
        parsed_groups.append(parsed)
    return parsed_groups


def _labels(count: int, labels: Sequence[str] | None) -> list[str]:
    if labels is None:
        return [f"group_{index}" for index in range(1, count + 1)]
    if len(labels) != count or len(set(labels)) != count:
        raise StatisticalCalculationError("Las etiquetas de grupos deben ser únicas y completas.")
    return list(labels)


def _means(groups: Sequence[Sequence[float]]) -> list[float]:
    return [sum(group) / len(group) for group in groups]


def _within_sum_squares(groups: Sequence[Sequence[float]], means: Sequence[float]) -> float:
    return sum(
        sum((value - mean) ** 2 for value in group)
        for group, mean in zip(groups, means, strict=True)
    )


def anova(groups: Sequence[Sequence[object]]) -> TechniqueResult:
    """Calculate one-way ANOVA's F statistic."""

    parsed = _groups(groups)
    means = _means(parsed)
    total = sum(len(group) for group in parsed)
    grand_mean = sum(sum(group) for group in parsed) / total
    between = sum(
        len(group) * (mean - grand_mean) ** 2 for group, mean in zip(parsed, means, strict=True)
    )
    within = _within_sum_squares(parsed, means)
    df_between = len(parsed) - 1
    df_within = total - len(parsed)
    mean_within = within / df_within
    if mean_within == 0:
        raise StatisticalCalculationError("La varianza intragrupo es cero; F no está definido.")
    f_statistic = (between / df_between) / mean_within
    omega_squared = max(
        0.0,
        (between - df_between * mean_within) / (between + within + mean_within),
    )
    return TechniqueResult(
        "anova",
        {
            "n": float(total),
            "f_statistic": f_statistic,
            "degrees_of_freedom_between": float(df_between),
            "degrees_of_freedom_within": float(df_within),
            "p_value": f_survival(f_statistic, float(df_between), float(df_within)),
            "eta_squared": between / (between + within),
            "omega_squared": omega_squared,
        },
    )


def anova_welch(groups: Sequence[Sequence[object]]) -> TechniqueResult:
    """Calculate Welch's heteroscedastic one-way F statistic."""

    parsed = _groups(groups)
    means = _means(parsed)
    variances = [_sample_variance(group) for group in parsed]
    if any(variance == 0 for variance in variances):
        raise StatisticalCalculationError("Welch requiere varianza positiva en cada grupo.")
    weights = [len(group) / variance for group, variance in zip(parsed, variances, strict=True)]
    total_weight = sum(weights)
    weighted_mean = (
        sum(weight * mean for weight, mean in zip(weights, means, strict=True)) / total_weight
    )
    correction = sum(
        (1 - weight / total_weight) ** 2 / (len(group) - 1)
        for weight, group in zip(weights, parsed, strict=True)
    )
    degrees_of_freedom_between = len(parsed) - 1
    degrees_of_freedom_within = (
        (len(parsed) ** 2 - 1) / (3 * correction) if correction else float("inf")
    )
    numerator = sum(
        weight * (mean - weighted_mean) ** 2 for weight, mean in zip(weights, means, strict=True)
    )
    correction_factor = 1 + 2 * (len(parsed) - 2) / (len(parsed) ** 2 - 1) * correction
    f_statistic = (numerator / degrees_of_freedom_between) / correction_factor
    return TechniqueResult(
        "anova_welch",
        {
            "n": float(sum(len(group) for group in parsed)),
            "f_statistic": f_statistic,
            "degrees_of_freedom_between": float(degrees_of_freedom_between),
            "degrees_of_freedom_within": degrees_of_freedom_within,
            "p_value": f_survival(
                f_statistic, float(degrees_of_freedom_between), degrees_of_freedom_within
            ),
        },
    )


def _pairwise_result(
    technique: str,
    groups: Sequence[Sequence[float]],
    labels: Sequence[str],
    standard_error,
    degrees_of_freedom,
    t_standard_error,
    warning: str,
) -> TechniqueResult:
    means = _means(groups)
    pair_count = len(groups) * (len(groups) - 1) // 2
    metrics: dict[str, float] = {"pair_count": float(pair_count)}
    for left_index, right_index in combinations(range(len(groups)), 2):
        prefix = f"{labels[left_index]}_vs_{labels[right_index]}"
        difference = means[left_index] - means[right_index]
        reported_standard_error = standard_error(left_index, right_index)
        inferential_standard_error = t_standard_error(left_index, right_index)
        pair_degrees_of_freedom = degrees_of_freedom(left_index, right_index)
        unadjusted_p_value = student_t_two_sided(
            abs(difference) / inferential_standard_error, pair_degrees_of_freedom
        )
        metrics[f"{prefix}.mean_difference"] = difference
        metrics[f"{prefix}.standard_error"] = reported_standard_error
        metrics[f"{prefix}.degrees_of_freedom"] = pair_degrees_of_freedom
        metrics[f"{prefix}.p_value"] = unadjusted_p_value
        metrics[f"{prefix}.p_value_bonferroni"] = min(1.0, unadjusted_p_value * pair_count)
    return TechniqueResult(technique, metrics, (warning,))


def tukey(
    groups: Sequence[Sequence[object]], labels: Sequence[str] | None = None
) -> TechniqueResult:
    """Return pooled-error pairwise mean differences for Tukey HSD."""

    parsed = _groups(groups)
    names = _labels(len(parsed), labels)
    means = _means(parsed)
    total = sum(len(group) for group in parsed)
    df_within = total - len(parsed)
    mean_square_within = _within_sum_squares(parsed, means) / df_within
    if mean_square_within == 0:
        raise StatisticalCalculationError("Tukey requiere varianza intragrupo positiva.")

    def standard_error(left: int, right: int) -> float:
        return math.sqrt(mean_square_within / 2 * (1 / len(parsed[left]) + 1 / len(parsed[right])))

    def degrees_of_freedom(_left: int, _right: int) -> float:
        return float(df_within)

    def t_standard_error(left: int, right: int) -> float:
        return math.sqrt(mean_square_within * (1 / len(parsed[left]) + 1 / len(parsed[right])))

    return _pairwise_result(
        "tukey",
        parsed,
        names,
        standard_error,
        degrees_of_freedom,
        t_standard_error,
        "Se informan p-valores t por par y ajuste Bonferroni conservador; "
        "no sustituyen el valor crítico de rango studentizado de Tukey.",
    )


def games_howell(
    groups: Sequence[Sequence[object]], labels: Sequence[str] | None = None
) -> TechniqueResult:
    """Return heteroscedastic pairwise differences for Games–Howell."""

    parsed = _groups(groups)
    names = _labels(len(parsed), labels)
    variances = [_sample_variance(group) for group in parsed]
    if any(variance == 0 for variance in variances):
        raise StatisticalCalculationError("Games–Howell requiere varianza positiva en cada grupo.")

    def standard_error(left: int, right: int) -> float:
        return math.sqrt(
            variances[left] / len(parsed[left]) + variances[right] / len(parsed[right])
        )

    def degrees_of_freedom(left: int, right: int) -> float:
        left_component = variances[left] / len(parsed[left])
        right_component = variances[right] / len(parsed[right])
        denominator = left_component**2 / (len(parsed[left]) - 1) + right_component**2 / (
            len(parsed[right]) - 1
        )
        return (left_component + right_component) ** 2 / denominator

    return _pairwise_result(
        "games_howell",
        parsed,
        names,
        standard_error,
        degrees_of_freedom,
        standard_error,
        "Se informan p-valores Welch por par y ajuste Bonferroni conservador; "
        "no sustituyen la distribución studentizada de Games–Howell.",
    )
