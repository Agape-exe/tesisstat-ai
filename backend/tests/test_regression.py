from math import isclose

from pytest import raises

from app.modules.statistics.inferential import StatisticalCalculationError
from app.modules.statistics.regression import (
    ancova,
    linear_regression_multiple,
    linear_regression_simple,
)


def test_simple_regression_returns_reference_coefficients():
    result = linear_regression_simple([1, 2, 3, 4], [2, 4, 6, 8])

    assert isclose(result.metrics["intercept"], 0)
    assert isclose(result.metrics["slope"], 2)
    assert isclose(result.metrics["r_squared"], 1)
    assert result.metrics["model_p_value"] == 0


def test_multiple_regression_returns_reference_coefficients():
    result = linear_regression_multiple(
        [[1, 2], [2, 1], [3, 4], [4, 3], [5, 6], [6, 5]],
        [1 + 2 * row[0] + 3 * row[1] for row in [[1, 2], [2, 1], [3, 4], [4, 3], [5, 6], [6, 5]]],
    )

    assert isclose(result.metrics["intercept"], 1)
    assert isclose(result.metrics["beta_1"], 2)
    assert isclose(result.metrics["beta_2"], 3)
    assert isclose(result.metrics["r_squared"], 1)
    assert result.metrics["model_p_value"] == 0


def test_ancova_returns_group_effect_and_covariate_coefficient():
    result = ancova(
        [3, 5, 5, 7, 9, 7],
        ["A", "A", "B", "B", "B", "A"],
        [1, 2, 1, 2, 3, 3],
    )

    assert result.metrics["group_count"] == 2
    assert isclose(result.metrics["group_B_effect"], 2)
    assert isclose(result.metrics["covariate_beta"], 2)
    assert result.metrics["model_p_value"] == 0


def test_regression_rejects_singular_design_and_small_samples():
    with raises(StatisticalCalculationError, match="singular"):
        linear_regression_multiple([[1, 1], [2, 2], [3, 3], [4, 4]], [2, 4, 6, 8])
    with raises(StatisticalCalculationError, match="tres pares"):
        linear_regression_simple([1, 2], [2, 4])
