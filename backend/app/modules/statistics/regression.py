"""Deterministic linear regression and ANCOVA calculations."""

from __future__ import annotations

import math
from collections.abc import Sequence

from .inferential import StatisticalCalculationError, TechniqueResult, _number, _paired_numbers


def _solve(matrix: list[list[float]], vector: list[float]) -> list[float]:
    """Solve a small linear system with Gaussian elimination and pivoting."""

    size = len(vector)
    augmented = [row[:] + [value] for row, value in zip(matrix, vector, strict=True)]
    for column in range(size):
        pivot = max(range(column, size), key=lambda row: abs(augmented[row][column]))
        if abs(augmented[pivot][column]) < 1e-12:
            raise StatisticalCalculationError("La matriz de diseño es singular o colineal.")
        augmented[column], augmented[pivot] = augmented[pivot], augmented[column]
        divisor = augmented[column][column]
        augmented[column] = [value / divisor for value in augmented[column]]
        for row in range(size):
            if row == column:
                continue
            factor = augmented[row][column]
            augmented[row] = [
                current - factor * pivot_value
                for current, pivot_value in zip(augmented[row], augmented[column], strict=True)
            ]
    return [augmented[index][-1] for index in range(size)]


def _fit_linear(
    features: Sequence[Sequence[float]], outcomes: Sequence[float]
) -> tuple[list[float], float, float]:
    if not features or len(features) != len(outcomes):
        raise StatisticalCalculationError("La matriz de diseño no puede estar vacía.")
    predictor_count = len(features[0])
    if any(len(row) != predictor_count for row in features):
        raise StatisticalCalculationError("Todas las filas deben tener los mismos predictores.")
    if len(features) <= predictor_count + 1:
        raise StatisticalCalculationError("La regresión requiere más observaciones que parámetros.")
    design = [[1.0, *row] for row in features]
    columns = len(design[0])
    gram = [
        [sum(row[left] * row[right] for row in design) for right in range(columns)]
        for left in range(columns)
    ]
    target = [
        sum(row[index] * outcome for row, outcome in zip(design, outcomes, strict=True))
        for index in range(columns)
    ]
    coefficients = _solve(gram, target)
    predictions = [
        sum(coefficient * value for coefficient, value in zip(coefficients, row, strict=True))
        for row in design
    ]
    mean_outcome = sum(outcomes) / len(outcomes)
    residual_sum = sum(
        (outcome - prediction) ** 2
        for outcome, prediction in zip(outcomes, predictions, strict=True)
    )
    total_sum = sum((outcome - mean_outcome) ** 2 for outcome in outcomes)
    if total_sum == 0:
        raise StatisticalCalculationError("La variable dependiente es constante.")
    r_squared = 1 - residual_sum / total_sum
    residual_df = len(outcomes) - columns
    residual_standard_error = math.sqrt(residual_sum / residual_df) if residual_df > 0 else 0.0
    return coefficients, r_squared, residual_standard_error


def linear_regression_simple(x: Sequence[object], y: Sequence[object]) -> TechniqueResult:
    """Fit y = intercept + slope*x using complete finite pairs."""

    values_x, values_y = _paired_numbers(x, y)
    if len(values_x) < 3:
        raise StatisticalCalculationError(
            "La regresión simple requiere al menos tres pares válidos."
        )
    coefficients, r_squared, residual_error = _fit_linear([[value] for value in values_x], values_y)
    return TechniqueResult(
        "linear_regression_simple",
        {
            "n": float(len(values_x)),
            "intercept": coefficients[0],
            "slope": coefficients[1],
            "r_squared": r_squared,
            "residual_standard_error": residual_error,
        },
    )


def linear_regression_multiple(
    predictors: Sequence[Sequence[object]], outcome: Sequence[object]
) -> TechniqueResult:
    """Fit a multiple linear model with an intercept."""

    if not predictors or len(predictors) != len(outcome):
        raise StatisticalCalculationError(
            "Los predictores y la respuesta deben tener igual cantidad de filas."
        )
    width = len(predictors[0])
    if width < 2:
        raise StatisticalCalculationError(
            "La regresión múltiple requiere al menos dos predictores."
        )
    complete_features: list[list[float]] = []
    complete_outcomes: list[float] = []
    for row, value in zip(predictors, outcome, strict=True):
        if len(row) != width:
            raise StatisticalCalculationError("Todas las filas deben tener los mismos predictores.")
        parsed_row = [_number(item) for item in row]
        parsed_outcome = _number(value)
        if parsed_outcome is not None and all(item is not None for item in parsed_row):
            complete_features.append([float(item) for item in parsed_row])
            complete_outcomes.append(parsed_outcome)
    coefficients, r_squared, residual_error = _fit_linear(complete_features, complete_outcomes)
    metrics = {
        "n": float(len(complete_outcomes)),
        "predictor_count": float(width),
        "intercept": coefficients[0],
        "r_squared": r_squared,
        "residual_standard_error": residual_error,
    }
    metrics.update(
        {f"beta_{index}": coefficient for index, coefficient in enumerate(coefficients[1:], 1)}
    )
    return TechniqueResult("linear_regression_multiple", metrics)


def ancova(
    outcome: Sequence[object], group: Sequence[object], covariate: Sequence[object]
) -> TechniqueResult:
    """Fit a one-covariate ANCOVA through group indicators and a covariate."""

    if not (len(outcome) == len(group) == len(covariate)):
        raise StatisticalCalculationError("ANCOVA requiere columnas con igual cantidad de filas.")
    group_values = sorted(
        {str(value).strip() for value in group if value is not None and str(value).strip()}
    )
    if len(group_values) < 2:
        raise StatisticalCalculationError("ANCOVA requiere al menos dos grupos.")
    features: list[list[object]] = []
    outcomes: list[object] = []
    for outcome_value, group_value, covariate_value in zip(outcome, group, covariate, strict=True):
        parsed_outcome = _number(outcome_value)
        parsed_covariate = _number(covariate_value)
        if parsed_outcome is None or parsed_covariate is None or group_value is None:
            continue
        current_group = str(group_value).strip()
        features.append(
            [
                *[1.0 if current_group == category else 0.0 for category in group_values[1:]],
                parsed_covariate,
            ]
        )
        outcomes.append(parsed_outcome)
    coefficients, r_squared, residual_error = _fit_linear(
        [[float(value) for value in row] for row in features],
        [float(value) for value in outcomes],
    )
    metrics = {
        "n": float(len(outcomes)),
        "group_count": float(len(group_values)),
        "r_squared": r_squared,
        "residual_standard_error": residual_error,
        "covariate_beta": coefficients[-1],
    }
    metrics.update(
        {
            f"group_{category}_effect": coefficients[index]
            for index, category in enumerate(group_values[1:], 1)
        }
    )
    return TechniqueResult("ancova", metrics)
