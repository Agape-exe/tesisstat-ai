from math import isclose

from app.modules.statistics.assumptions import (
    homogeneity,
    homoscedasticity,
    independence,
    normality,
)


def test_normality_returns_jarque_bera_diagnostic_for_symmetric_values():
    result = normality(list(range(1, 21)))

    assert result.statistic is not None
    assert result.p_value is not None
    assert result.status == "passed"


def test_normality_reports_not_checked_for_small_samples():
    result = normality([1, 2, 3, 4])

    assert result.status == "not_checked"
    assert result.statistic is None


def test_homogeneity_returns_brown_forsythe_result():
    result = homogeneity([[1, 2, 3, 4], [2, 3, 4, 5], [10, 11, 12, 13]])

    assert result.statistic is not None
    assert result.p_value is not None
    assert result.status in {"passed", "failed"}


def test_homoscedasticity_returns_lm_screening_and_independence_is_explicit():
    result = homoscedasticity([1, 2, 3, 4, 5, 6], [1, -1, 1, -1, 1, -1])

    assert isclose(result.statistic or 0, 0)
    assert result.status == "passed"
    assert independence().status == "not_checked"
