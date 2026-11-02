"""Deterministic rank-based comparison techniques."""

from __future__ import annotations

from collections.abc import Sequence

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
    return TechniqueResult(
        "mann_whitney",
        {
            "n_left": float(len(x)),
            "n_right": float(len(y)),
            "u": min(u_left, u_right),
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
    return TechniqueResult(
        "wilcoxon",
        {
            "n": float(len(differences)),
            "w_positive": positive,
            "w_negative": negative,
            "w": min(positive, negative),
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
    return TechniqueResult(
        "kruskal_wallis",
        {"n": float(total), "h": h, "degrees_of_freedom": float(len(groups) - 1)},
    )
