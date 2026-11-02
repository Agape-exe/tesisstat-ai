"""Deterministic rank-based comparison techniques."""

from __future__ import annotations

from collections.abc import Sequence

from .distributions import chi_square_survival, normal_two_sided
from .inferential import (
    StatisticalCalculationError,
    TechniqueResult,
    _number,
    _paired_numbers,
)


def _numeric_group(values: Sequence[object]) -> list[float]:
    result = []
    for value in values:
        parsed = _number(value)
        if parsed is not None:
            result.append(parsed)
    if len(result) < 2:
        raise StatisticalCalculationError("Cada grupo requiere al menos dos valores válidos.")
    return result


def _rank(values: Sequence[float]) -> list[float]:
    ordered = sorted(enumerate(values), key=lambda item: item[1])
    ranks = [0.0] * len(values)
    index = 0
    while index < len(ordered):
        end = index + 1
        while end < len(ordered) and ordered[end][1] == ordered[index][1]:
            end += 1
        rank = (index + 1 + end) / 2
        for position in range(index, end):
            ranks[ordered[position][0]] = rank
        index = end
    return ranks


def mann_whitney(left: Sequence[object], right: Sequence[object]) -> TechniqueResult:
    """Calculate the smaller Mann–Whitney U statistic, with average ties."""

    x = _numeric_group(left)
    y = _numeric_group(right)
    ranks = _rank(x + y)
    rank_sum_left = sum(ranks[: len(x)])
    u_left = rank_sum_left - len(x) * (len(x) + 1) / 2
    u_right = len(x) * len(y) - u_left
    u = min(u_left, u_right)
    total = len(x) + len(y)
    tie_counts: dict[float, int] = {}
    for value in x + y:
        tie_counts[value] = tie_counts.get(value, 0) + 1
    tie_adjustment = sum(count**3 - count for count in tie_counts.values())
    variance = len(x) * len(y) / 12 * ((total + 1) - tie_adjustment / (total * (total - 1)))
    z_statistic = max(0.0, abs(u - len(x) * len(y) / 2) - 0.5) / variance**0.5
    return TechniqueResult(
        "mann_whitney",
        {
            "n_left": float(len(x)),
            "n_right": float(len(y)),
            "u": u,
            "z_statistic": z_statistic,
            "p_value": normal_two_sided(z_statistic),
            "rank_biserial_effect": 1 - 2 * u / (len(x) * len(y)),
        },
    )


def wilcoxon(left: Sequence[object], right: Sequence[object]) -> TechniqueResult:
    """Calculate the signed-rank statistic, dropping zero differences."""

    x, y = _paired_numbers(left, right)
    differences = [a - b for a, b in zip(x, y, strict=True) if a != b]
    if len(differences) < 2:
        raise StatisticalCalculationError("Wilcoxon requiere al menos dos diferencias no nulas.")
    ranks = _rank([abs(value) for value in differences])
    positive = sum(
        rank for rank, difference in zip(ranks, differences, strict=True) if difference > 0
    )
    negative = sum(
        rank for rank, difference in zip(ranks, differences, strict=True) if difference < 0
    )
    statistic = min(positive, negative)
    count = len(differences)
    tie_counts: dict[float, int] = {}
    for value in (abs(item) for item in differences):
        tie_counts[value] = tie_counts.get(value, 0) + 1
    variance = (
        count * (count + 1) * (2 * count + 1)
        - sum(size * (size + 1) * (2 * size + 1) / 2 for size in tie_counts.values())
    ) / 24
    z_statistic = max(0.0, abs(statistic - count * (count + 1) / 4) - 0.5) / variance**0.5
    return TechniqueResult(
        "wilcoxon",
        {
            "n": float(len(differences)),
            "w_positive": positive,
            "w_negative": negative,
            "w": statistic,
            "z_statistic": z_statistic,
            "p_value": normal_two_sided(z_statistic),
            "rank_effect": z_statistic / count**0.5,
        },
    )


def kruskal_wallis(groups: Sequence[Sequence[object]]) -> TechniqueResult:
    """Calculate the Kruskal–Wallis H statistic with average ties."""

    if len(groups) < 3:
        raise StatisticalCalculationError("Kruskal–Wallis requiere al menos tres grupos.")
    numeric_groups = [_numeric_group(group) for group in groups]
    values = [value for group in numeric_groups for value in group]
    ranks = _rank(values)
    offset = 0
    rank_sums: list[float] = []
    for group in numeric_groups:
        rank_sums.append(sum(ranks[offset : offset + len(group)]))
        offset += len(group)
    total = len(values)
    h = 12 / (total * (total + 1)) * sum(
        rank_sum**2 / len(group) for rank_sum, group in zip(rank_sums, numeric_groups, strict=True)
    ) - 3 * (total + 1)
    tie_counts: dict[float, int] = {}
    for value in values:
        tie_counts[value] = tie_counts.get(value, 0) + 1
    correction = 1 - sum(count**3 - count for count in tie_counts.values()) / (total**3 - total)
    if correction <= 0:
        raise StatisticalCalculationError(
            "Kruskal–Wallis no está definido cuando todos los rangos empatan."
        )
    h /= correction
    degrees_of_freedom = len(groups) - 1
    return TechniqueResult(
        "kruskal_wallis",
        {
            "n": float(total),
            "h": h,
            "degrees_of_freedom": float(degrees_of_freedom),
            "p_value": chi_square_survival(h, float(degrees_of_freedom)),
            "tie_correction": correction,
        },
    )
