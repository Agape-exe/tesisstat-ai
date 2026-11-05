from math import isclose

from pytest import raises

from app.modules.statistics.anova import anova, anova_welch, games_howell, tukey
from app.modules.statistics.inferential import StatisticalCalculationError


def test_anova_returns_reference_f_statistic():
    result = anova([[1, 2, 3], [4, 5, 6], [7, 8, 9]])

    assert isclose(result.metrics["f_statistic"], 27.0)
    assert result.metrics["degrees_of_freedom_between"] == 2
    assert result.metrics["degrees_of_freedom_within"] == 6
    assert isclose(result.metrics["eta_squared"], 0.9)
    assert isclose(result.metrics["omega_squared"], 52 / 61)


def test_welch_anova_returns_finite_statistic_and_fractional_df():
    result = anova_welch([[1, 2, 3], [4, 6, 8], [9, 10, 12]])

    assert result.metrics["f_statistic"] > 0
    assert result.metrics["degrees_of_freedom_within"] > 2


def test_tukey_returns_pairwise_pooled_standard_errors():
    result = tukey([[1, 2, 3], [4, 5, 6], [7, 8, 9]], ["A", "B", "C"])

    assert result.metrics["pair_count"] == 3
    assert isclose(result.metrics["A_vs_B.mean_difference"], -3)
    assert isclose(result.metrics["A_vs_B.standard_error"], 1 / 3**0.5)
    assert isclose(result.metrics["A_vs_B.p_value"], 0.010401720935464015)
    assert isclose(result.metrics["A_vs_B.p_value_bonferroni"], 0.031205162806392044)
    assert "Bonferroni conservador" in result.warnings[0]


def test_games_howell_returns_pairwise_welch_degrees_of_freedom():
    result = games_howell([[1, 2, 3], [4, 6, 8], [9, 10, 12]], ["A", "B", "C"])

    assert result.metrics["pair_count"] == 3
    assert result.metrics["A_vs_B.degrees_of_freedom"] > 2
    assert 0 <= result.metrics["A_vs_B.p_value_bonferroni"] <= 1
    assert "Bonferroni conservador" in result.warnings[0]


def test_anova_family_rejects_insufficient_groups_or_zero_variance():
    with raises(StatisticalCalculationError, match="tres grupos"):
        anova([[1, 2], [3, 4]])
    with raises(StatisticalCalculationError, match="varianza positiva"):
        games_howell([[1, 1], [2, 3], [4, 5]])
