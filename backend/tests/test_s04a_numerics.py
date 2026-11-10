"""Independent references: SciPy for custom algorithms; hand arithmetic for summaries/alpha.

No production minimum technique delegates to the reference SciPy functions below.
All inference validated here is two-sided; no claim is made for unilateral directions.
"""

import math

import pytest
from scipy import stats

from app.modules.statistics.comparisons import t_independent, t_paired, t_welch
from app.modules.statistics.descriptive import describe_categorical, describe_numeric
from app.modules.statistics.inferential import (
    StatisticalCalculationError,
    cronbach_alpha,
    pearson,
    spearman,
)
from app.modules.statistics.nonparametric import mann_whitney, wilcoxon


def close(actual, expected, probability=False):
    assert actual == pytest.approx(expected, abs=1e-8, rel=1e-5 if probability else 1e-6)


@pytest.mark.parametrize(
    "x,y",
    [
        ([1, 2, 3], [4, 5, 6]),
        ([1, 2, 4, 9, 13], [2, 4, 8]),
        ([1, 1, 1], [1, 2, 3, 7, 100, 120]),
        ([0.001, 0.002, 0.008], [-2, 3, 5, 7]),
    ],
)
@pytest.mark.parametrize("function,pooled", [(t_welch, False), (t_independent, True)])
def test_two_group_reference(x, y, function, pooled):
    expected = stats.ttest_ind(x, y, equal_var=pooled, alternative="two-sided")
    actual = function([*x, None], [None, *y]).metrics
    assert (actual["n_left"], actual["n_right"]) == (len(x), len(y))
    close(actual["t_statistic"], expected.statistic)
    close(actual["degrees_of_freedom"], expected.df)
    close(actual["p_value"], expected.pvalue, True)
    ci = expected.confidence_interval(0.95)
    close(actual["mean_difference_ci_95_low"], ci.low)
    close(actual["mean_difference_ci_95_high"], ci.high)


def test_paired_reference_and_orientation_with_incomplete_pairs():
    x, y = [1, 3, 5, 7], [3, 3, 4, 11]
    expected = stats.ttest_rel(x, y, alternative="two-sided")
    actual = t_paired([*x, None, 100], [*y, 999, None]).metrics
    assert actual["n"] == 4
    close(actual["mean_difference"], -1.25)
    close(actual["t_statistic"], expected.statistic)
    close(actual["degrees_of_freedom"], 3)
    close(actual["p_value"], expected.pvalue, True)
    close(t_paired(y, x).metrics["t_statistic"], -actual["t_statistic"])


@pytest.mark.parametrize(
    "x,y",
    [
        ([1, 2, 3, 4, 5], [1, 2, 4, 3, 5]),
        ([1, 1, 2, 3, 5, 5], [2, 3, 3, 5, 1, 6]),
        ([1, 2, 3, 4], [4, 3, 2, 1]),
        ([1, 2, 3, 4, 5], [1, 4, 9, 16, 25]),
    ],
)
@pytest.mark.parametrize(
    "function,reference,key", [(pearson, stats.pearsonr, "r"), (spearman, stats.spearmanr, "rho")]
)
def test_correlations_reference_joint_missing_and_ties(x, y, function, reference, key):
    expected = reference(x, y, alternative="two-sided")
    actual = function([*x, None, 42], [*y, 100, None]).metrics
    assert actual["n"] == len(x)
    close(actual[key], expected.statistic)
    close(actual["p_value"], expected.pvalue, True)
    assert all(math.isfinite(v) for v in actual.values())


@pytest.mark.parametrize(
    "x,y,method",
    [
        ([1, 2, 3], [4, 5, 6], "exact"),
        ([1, 4, 6, 8], [2, 3, 5], "exact"),
        ([1, 1, 2], [2, 3, 4], "asymptotic"),
        (list(range(15)), list(range(12, 25)), "asymptotic"),
    ],
)
def test_mann_whitney_reference_methods(x, y, method):
    expected = stats.mannwhitneyu(x, y, method=method, use_continuity=True, alternative="two-sided")
    actual = mann_whitney(x, y).metrics
    close(actual["u"], min(expected.statistic, len(x) * len(y) - expected.statistic))
    close(actual["p_value"], expected.pvalue, True)


@pytest.mark.parametrize(
    "d,method",
    [
        ([1, 2, 3], "exact"),
        ([1, -2, 3, -4, 5], "exact"),
        ([0, -1, -1], "asymptotic"),
        ([1, -1, 2, -2, 0, 4], "asymptotic"),
        ([0, 1, 2, 3], "asymptotic"),
        (list(range(1, 23)), "asymptotic"),
    ],
)
def test_wilcoxon_reference_zeros_ties_and_continuity(d, method):
    expected = stats.wilcoxon(
        d, zero_method="wilcox", correction=True, alternative="two-sided", method=method
    )
    actual = wilcoxon([*d, None], [*[0] * len(d), 50]).metrics
    assert actual["n"] == len([x for x in d if x])
    close(actual["w"], expected.statistic)
    close(actual["p_value"], expected.pvalue, True)


def test_hand_enumerated_exact_probabilities():
    # Two extreme allocations of 3 of 6 ranks / C(6,3).
    close(mann_whitney([1, 2, 3], [4, 5, 6]).metrics["p_value"], 2 / 20, True)
    # All-positive or all-negative among 2^3 sign assignments.
    close(wilcoxon([1, 2, 3], [0, 0, 0]).metrics["p_value"], 2 / 8, True)


def test_descriptive_hand_calculation_and_denominators():
    s = describe_numeric(["1", "2", "2", "4", None])
    assert (s.valid_count, s.missing_count) == (4, 1)
    assert (s.mean, s.median, s.modes) == (2.25, 2, [2])
    close(s.sample_variance, 19 / 12)
    close(s.sample_standard_deviation, math.sqrt(19 / 12))
    assert s.quantiles == {"p0": 1, "p25": 1.75, "p50": 2, "p75": 2.5, "p100": 4}
    assert describe_numeric([]).mean is None
    assert describe_numeric(["5"]).sample_variance is None
    assert describe_numeric(["5", "5"]).sample_variance == 0
    categorical = describe_categorical(["1", "2", "1", None])
    assert categorical.valid_count == 3
    close(categorical.frequencies[0].percentage, 200 / 3)


def test_alpha_hand_variances_complete_cases_and_negative():
    # Item variances 1 and 4, total variance 9; alpha = 2*(1-5/9).
    actual = cronbach_alpha([[1, 2], [2, 4], [3, 6], [None, 8]]).metrics
    assert actual["n"] == 3
    close(actual["alpha"], 8 / 9)
    # Item variances 1 and 7/3; total variance 4/3 => alpha = -3.
    negative = cronbach_alpha([[1, 4], [2, 1], [3, 2]])
    close(negative.metrics["alpha"], -3)
    assert any("negativo" in w for w in negative.warnings)


@pytest.mark.parametrize(
    "function,args",
    [
        (pearson, ([1, 1, 1], [1, 2, 3])),
        (spearman, ([1, 2], [2, 3])),
        (pearson, ([None] * 3, [1, 2, 3])),
        (t_welch, ([2, 2], [2, 2])),
        (t_independent, ([1], [1, 2])),
        (t_paired, ([1, 2], [1, 2])),
        (t_paired, ([1, None], [2, 3])),
        (mann_whitney, ([1, 1], [1, 1])),
        (wilcoxon, ([1, 2], [1, 2])),
        (wilcoxon, ([2, 2], [1, 2])),
        (cronbach_alpha, ([[1, 1], [1, 1]],)),
        (cronbach_alpha, ([[1], [2]],)),
        (pearson, ([1, 2, float("inf")], [1, 2, 3])),
    ],
)
def test_not_calculable_is_explicit(function, args):
    with pytest.raises(StatisticalCalculationError):
        function(*args)


def test_extreme_finite_inputs_never_return_nonfinite():
    for function, args in [
        (describe_numeric, (["1e308", "-1e308"],)),
        (t_welch, ([1e308, -1e308], [2, 3])),
        (cronbach_alpha, ([[1e308, 1e308], [-1e308, 1e308]],)),
    ]:
        with pytest.raises((ValueError, OverflowError)):
            function(*args)
