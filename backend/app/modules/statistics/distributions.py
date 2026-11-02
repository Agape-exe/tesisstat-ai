"""Small, dependency-free distribution survival functions for reported metrics."""

from __future__ import annotations

import math


def _beta_fraction(a: float, b: float, x: float) -> float:
    factor = math.exp(math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b))
    factor *= x**a * (1 - x) ** b / a
    c = 1.0
    d = 1.0 - (a + b) * x / (a + 1)
    d = 1e-30 if abs(d) < 1e-30 else d
    d = 1 / d
    result = d
    for index in range(1, 201):
        even = 2 * index
        numerator = index * (b - index) * x / ((a + even - 1) * (a + even))
        d = 1 + numerator * d
        c = 1 + numerator / c
        d = 1 / (1e-30 if abs(d) < 1e-30 else d)
        c = 1e-30 if abs(c) < 1e-30 else c
        result *= d * c
        numerator = -(a + index) * (a + b + index) * x / ((a + even) * (a + even + 1))
        d = 1 + numerator * d
        c = 1 + numerator / c
        d = 1 / (1e-30 if abs(d) < 1e-30 else d)
        c = 1e-30 if abs(c) < 1e-30 else c
        delta = d * c
        result *= delta
        if abs(delta - 1) < 3e-14:
            break
    return factor * result


def regularized_beta(a: float, b: float, x: float) -> float:
    if x <= 0:
        return 0.0
    if x >= 1:
        return 1.0
    if x < (a + 1) / (a + b + 2):
        return _beta_fraction(a, b, x)
    return 1 - _beta_fraction(b, a, 1 - x)


def f_survival(statistic: float, df_one: float, df_two: float) -> float:
    if statistic <= 0:
        return 1.0
    x = df_one * statistic / (df_one * statistic + df_two)
    return max(0.0, min(1.0, 1 - regularized_beta(df_one / 2, df_two / 2, x)))


def student_t_two_sided(statistic: float, degrees_of_freedom: float) -> float:
    if degrees_of_freedom <= 0:
        return float("nan")
    x = degrees_of_freedom / (degrees_of_freedom + statistic**2)
    return max(0.0, min(1.0, regularized_beta(degrees_of_freedom / 2, 0.5, x)))


def chi_square_survival(statistic: float, degrees_of_freedom: float) -> float:
    """Upper regularized gamma Q(a, x), using continued fractions or a series."""
    if statistic <= 0:
        return 1.0
    a = degrees_of_freedom / 2
    x = statistic / 2
    if x < a + 1:
        term = 1 / a
        total = term
        for index in range(1, 1000):
            term *= x / (a + index)
            total += term
            if abs(term) < abs(total) * 1e-14:
                break
        lower = total * math.exp(-x + a * math.log(x) - math.lgamma(a))
        return max(0.0, min(1.0, 1 - lower))
    tiny = 1e-30
    b = x + 1 - a
    c = 1 / tiny
    d = 1 / (b if abs(b) > tiny else tiny)
    fraction = d
    for index in range(1, 1000):
        coefficient = -index * (index - a)
        b += 2
        d = coefficient * d + b
        c = b + coefficient / c
        d = 1 / (d if abs(d) > tiny else tiny)
        delta = d * c
        fraction *= delta
        if abs(delta - 1) < 1e-14:
            break
    return max(0.0, min(1.0, math.exp(-x + a * math.log(x) - math.lgamma(a)) * fraction))
