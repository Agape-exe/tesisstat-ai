"""Deterministic rank-based comparison techniques."""

from __future__ import annotations

import math
from collections.abc import Sequence
from itertools import combinations, product

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


def _has_ties(values: Sequence[float]) -> bool:
    """Return whether a rank calculation needs averaged ranks."""

    return len(set(values)) != len(values)


def _exact_mann_whitney_p_value(n_left: int, n_right: int, observed_u: float) -> float:
    """Return the two-sided exact probability for the smaller U statistic."""

    total = n_left + n_right
    total_assignments = 0
    as_or_more_extreme = 0
    for selected in combinations(range(1, total + 1), n_left):
        u_left = sum(selected) - n_left * (n_left + 1) / 2
        smaller_u = min(u_left, n_left * n_right - u_left)
        total_assignments += 1
        if smaller_u <= observed_u:
            as_or_more_extreme += 1
    return as_or_more_extreme / total_assignments


def _exact_wilcoxon_p_value(ranks: Sequence[float], observed_w: float) -> float:
    """Return the two-sided exact probability for the smaller signed-rank sum."""

    total_rank = sum(ranks)
    total_assignments = 0
    as_or_more_extreme = 0
    for signs in product((False, True), repeat=len(ranks)):
        positive = sum(rank for rank, is_positive in zip(ranks, signs, strict=True) if is_positive)
        smaller_w = min(positive, total_rank - positive)
        total_assignments += 1
        if smaller_w <= observed_w:
            as_or_more_extreme += 1
    return as_or_more_extreme / total_assignments


def _kruskal_wallis_statistic(
    rank_sums: Sequence[float], group_sizes: Sequence[int], total: int, tie_correction: float
) -> float:
    """Calculate a tie-corrected Kruskal–Wallis H from rank sums."""

    statistic = 12 / (total * (total + 1)) * sum(
        rank_sum**2 / group_size
        for rank_sum, group_size in zip(rank_sums, group_sizes, strict=True)
    ) - 3 * (total + 1)
    return statistic / tie_correction


def _assignment_count(group_sizes: Sequence[int]) -> int:
    """Return the number of labelled rank assignments for fixed group sizes."""

    total = sum(group_sizes)
    count = math.factorial(total)
    for size in group_sizes:
        count //= math.factorial(size)
    return count


def _exact_kruskal_wallis_p_value(
    ranks: Sequence[float],
    group_sizes: Sequence[int],
    tie_correction: float,
    observed_h: float,
) -> float:
    """Return the right-tailed conditional permutation probability for H.

    Group sizes and the observed ranks stay fixed. This is practical only for
    the deliberately small assignment space selected by ``kruskal_wallis``.
    Equal ranks remain separate observations during enumeration, which gives
    each labelled allocation its appropriate probability.
    """

    total = len(ranks)
    assignments = 0
    as_or_more_extreme = 0

    def enumerate_groups(available: tuple[int, ...], rank_sums: tuple[float, ...]) -> None:
        nonlocal assignments, as_or_more_extreme
        group_index = len(rank_sums)
        if group_index == len(group_sizes) - 1:
            final_sums = (*rank_sums, sum(ranks[index] for index in available))
            statistic = _kruskal_wallis_statistic(final_sums, group_sizes, total, tie_correction)
            assignments += 1
            if statistic >= observed_h - 1e-12:
                as_or_more_extreme += 1
            return

        for selected in combinations(available, group_sizes[group_index]):
            selected_indices = set(selected)
            remaining = tuple(index for index in available if index not in selected_indices)
            enumerate_groups(
                remaining,
                (*rank_sums, sum(ranks[index] for index in selected)),
            )

    enumerate_groups(tuple(range(total)), ())
    return as_or_more_extreme / assignments


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
    if variance <= 0:
        raise StatisticalCalculationError(
            "Mann–Whitney no está definido cuando todos los rangos empatan."
        )
    z_statistic = max(0.0, abs(u - len(x) * len(y) / 2) - 0.5) / variance**0.5
    exact = total <= 20 and not _has_ties(x + y)
    warnings: tuple[str, ...] = ()
    if exact:
        p_value = _exact_mann_whitney_p_value(len(x), len(y), u)
        warnings = ("El p-valor es exacto por enumeración de permutaciones sin empates.",)
    else:
        p_value = normal_two_sided(z_statistic)
    if not exact and total < 20:
        warnings = (
            "El p-valor usa aproximación normal; interprétalo con cautela en muestras pequeñas.",
        )
    return TechniqueResult(
        "mann_whitney",
        {
            "n_left": float(len(x)),
            "n_right": float(len(y)),
            "u": u,
            "z_statistic": z_statistic,
            "p_value": p_value,
            "rank_biserial_effect": 1 - 2 * u / (len(x) * len(y)),
        },
        warnings,
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
    # Each tie block contributes (t^3-t)/2; singleton ranks subtract nothing.
    variance = (
        count * (count + 1) * (2 * count + 1)
        - sum(size**3 - size for size in tie_counts.values()) / 2
    ) / 24
    z_statistic = max(0.0, abs(statistic - count * (count + 1) / 4) - 0.5) / variance**0.5
    absolute_differences = [abs(item) for item in differences]
    exact = count <= 20 and len(differences) == len(x) and not _has_ties(absolute_differences)
    warnings: tuple[str, ...] = ()
    if exact:
        p_value = _exact_wilcoxon_p_value(ranks, statistic)
        warnings = ("El p-valor es exacto por enumeración de signos sin empates absolutos.",)
    else:
        p_value = normal_two_sided(z_statistic)
    if not exact and count < 20:
        warnings = (
            "El p-valor usa aproximación normal; interprétalo con cautela en muestras pequeñas.",
        )
    return TechniqueResult(
        "wilcoxon",
        {
            "n": float(len(differences)),
            "w_positive": positive,
            "w_negative": negative,
            "w": statistic,
            "z_statistic": z_statistic,
            "p_value": p_value,
            "rank_effect": z_statistic / count**0.5,
        },
        warnings,
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
    tie_counts: dict[float, int] = {}
    for value in values:
        tie_counts[value] = tie_counts.get(value, 0) + 1
    correction = 1 - sum(count**3 - count for count in tie_counts.values()) / (total**3 - total)
    if correction <= 0:
        raise StatisticalCalculationError(
            "Kruskal–Wallis no está definido cuando todos los rangos empatan."
        )
    group_sizes = [len(group) for group in numeric_groups]
    h = _kruskal_wallis_statistic(rank_sums, group_sizes, total, correction)
    degrees_of_freedom = len(groups) - 1
    assignment_count = _assignment_count(group_sizes)
    exact = total <= 10 and assignment_count <= 50_000
    warnings: tuple[str, ...] = ()
    if exact:
        p_value = _exact_kruskal_wallis_p_value(ranks, group_sizes, correction, h)
        warnings = (
            "El p-valor es exacto por enumeración de asignaciones condicionales de rangos.",
        )
    else:
        p_value = chi_square_survival(h, float(degrees_of_freedom))
        if total <= 10:
            warnings = (
                "El p-valor usa aproximación chi-cuadrado porque el espacio exacto de "
                "asignaciones excede el límite determinista de 50 000.",
            )
    return TechniqueResult(
        "kruskal_wallis",
        {
            "n": float(total),
            "h": h,
            "degrees_of_freedom": float(degrees_of_freedom),
            "p_value": p_value,
            "tie_correction": correction,
            "epsilon_squared": max(0.0, (h - len(groups) + 1) / (total - len(groups))),
        },
        warnings,
    )
