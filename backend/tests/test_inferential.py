from math import isclose

from pytest import raises

from app.modules.statistics.inferential import (
    StatisticalCalculationError,
    chi_square,
    cronbach_alpha,
    fisher_exact,
    pearson,
    spearman,
)


def test_pearson_returns_perfect_linear_association():
    result = pearson([1, 2, 3, 4], [3, 5, 7, 9])

    assert result.technique == "pearson"
    assert result.metrics["n"] == 4
    assert isclose(result.metrics["r"], 1.0)
    assert result.metrics["p_value"] == 0


def test_spearman_uses_ranks_and_ignores_missing_pairs():
    result = spearman([1, 2, 3, None, 4], [4, 3, 2, 9, 1])

    assert result.metrics["n"] == 4
    assert isclose(result.metrics["rho"], -1.0)


def test_chi_square_returns_reference_statistic():
    result = chi_square(["A", "A", "A", "B", "B", "B"], ["X", "X", "Y", "X", "Y", "Y"])

    assert isclose(result.metrics["chi_square"], 2 / 3)
    assert result.metrics["degrees_of_freedom"] == 1
    assert isclose(result.metrics["p_value"], 0.4142161782425252)
    assert isclose(result.metrics["cramers_v"], 1 / 3)
    assert result.warnings


def test_fisher_exact_returns_two_by_two_result():
    result = fisher_exact(["A", "A", "A", "B", "B", "B"], ["X", "X", "Y", "X", "Y", "Y"])

    assert result.metrics["n"] == 6
    assert isclose(result.metrics["odds_ratio"], 4.0)
    assert isclose(result.metrics["p_value"], 1.0)


def test_cronbach_alpha_returns_one_for_identical_item_scales():
    result = cronbach_alpha([[1, 1, 1], [2, 2, 2], [3, 3, 3]])

    assert result.metrics["items"] == 3
    assert isclose(result.metrics["alpha"], 1.0)


def test_inferential_functions_reject_invalid_or_insufficient_samples():
    with raises(StatisticalCalculationError, match="tres"):
        pearson([1, 2], [3, 4])
    with raises(StatisticalCalculationError, match="constante"):
        spearman([1, 1, 1], [2, 3, 4])
    with raises(StatisticalCalculationError, match="2 × 2"):
        fisher_exact(["A", "A", "A"], ["X", "Y", "X"])
