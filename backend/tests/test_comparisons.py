from math import isclose

from pytest import raises

from app.modules.statistics.comparisons import t_independent, t_paired, t_welch
from app.modules.statistics.inferential import StatisticalCalculationError


def test_independent_t_returns_reference_statistic_and_degrees_of_freedom():
    result = t_independent([1, 2, 3], [4, 5, 6])

    assert result.technique == "t_independent"
    assert result.metrics["degrees_of_freedom"] == 4
    assert isclose(result.metrics["t_statistic"], -3.6742346141747673)
    assert isclose(result.metrics["p_value"], 0.021311641128756727)
    assert isclose(result.metrics["cohens_d"], -3.0)


def test_welch_t_uses_satterthwaite_degrees_of_freedom():
    result = t_welch([1, 2, 3], [4, 6, 8])

    assert result.technique == "t_welch"
    assert result.metrics["t_statistic"] < 0
    assert result.metrics["degrees_of_freedom"] > 2
    assert result.metrics["degrees_of_freedom"] < 4


def test_paired_t_uses_complete_differences():
    result = t_paired([1, 2, 3, None], [2, 2, 4, 100])

    assert result.metrics["n"] == 3
    assert result.metrics["degrees_of_freedom"] == 2
    assert isclose(result.metrics["t_statistic"], -2.0)


def test_t_tests_reject_insufficient_groups():
    with raises(StatisticalCalculationError, match="dos valores"):
        t_independent([1], [2, 3])
    with raises(StatisticalCalculationError, match="dos pares"):
        t_paired([1], [2])
