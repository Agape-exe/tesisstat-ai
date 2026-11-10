from math import isclose

from pytest import raises

from app.modules.statistics.inferential import StatisticalCalculationError
from app.modules.statistics.nonparametric import kruskal_wallis, mann_whitney, wilcoxon


def test_mann_whitney_returns_zero_for_separated_groups():
    result = mann_whitney([1, 2, 3], [4, 5, 6])

    assert result.metrics["u"] == 0
    assert result.metrics["n_left"] == 3
    assert isclose(result.metrics["p_value"], 0.1)
    assert result.metrics["rank_biserial_effect"] == 1
    assert "exacto" in result.warnings[0]


def test_wilcoxon_uses_exact_probability_without_tied_absolute_differences():
    result = wilcoxon([1, 2, 3], [0, 0, 0])

    assert result.metrics["w"] == 0
    assert isclose(result.metrics["p_value"], 0.25)
    assert "exacto" in result.warnings[0]


def test_wilcoxon_uses_average_ranks_for_tied_absolute_differences():
    result = wilcoxon([1, 2, 3], [2, 2, 4])

    assert result.metrics["n"] == 2
    assert result.metrics["w_positive"] == 0
    assert result.metrics["w_negative"] == 3
    assert result.metrics["w"] == 0
    # Var(W+) = (30 - (2**3 - 2)/2) / 24 = 1.125, continuity 0.5.
    assert isclose(result.metrics["p_value"], 0.34577858615116025)
    assert "aproximación normal" in result.warnings[0]


def test_kruskal_wallis_returns_reference_statistic():
    result = kruskal_wallis([[1, 2], [3, 4], [5, 6]])

    assert result.metrics["degrees_of_freedom"] == 2
    assert isclose(result.metrics["h"], 4.571428571428569)
    # Exact conditional enumeration: 6 allocations at least this extreme / 90.
    assert isclose(result.metrics["p_value"], 1 / 15)
    assert "exacto" in result.warnings[0]


def test_kruskal_wallis_applies_tie_correction_and_reports_p_value():
    result = kruskal_wallis([[1, 1, 2], [2, 3, 3], [1, 3, 4]])

    assert isclose(result.metrics["tie_correction"], 0.925)
    assert isclose(result.metrics["h"], 3.0510510510510516)
    # With nine observations the exact conditional distribution is still tractable.
    assert isclose(result.metrics["p_value"], 0.28214285714285714)
    assert "exacto" in result.warnings[0]


def test_kruskal_wallis_uses_chi_square_when_exact_enumeration_is_too_large():
    result = kruskal_wallis([[1, 2], [3, 4], [5, 6], [7, 8], [9, 10]])

    assert isclose(result.metrics["p_value"], 0.06828984590243155)
    assert "chi-cuadrado" in result.warnings[0]


def test_kruskal_wallis_reports_epsilon_squared_reference_effect():
    result = kruskal_wallis([[1, 2, 3], [4, 5, 6], [7, 8, 9]])

    assert isclose(result.metrics["epsilon_squared"], 0.8666666666666671)


def test_nonparametric_functions_reject_invalid_group_counts():
    with raises(StatisticalCalculationError, match="tres grupos"):
        kruskal_wallis([[1, 2], [3, 4]])
    with raises(StatisticalCalculationError, match="dos diferencias"):
        wilcoxon([1, 2], [1, 2])


def test_mann_whitney_rejects_completely_tied_ranks():
    with raises(StatisticalCalculationError, match="todos los rangos empatan"):
        mann_whitney([1, 1], [1, 1])
