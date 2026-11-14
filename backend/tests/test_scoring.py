import json
from pathlib import Path

import pytest

from app.modules.statistics.inferential import StatisticalCalculationError
from app.modules.statistics.scoring import (
    ItemScoringSpec,
    ScoringRuleSpec,
    ScoringValidationError,
    calculate_cronbach_reliability,
    calculate_scores,
)

ROOT = Path(__file__).resolve().parents[2]
CASES = json.loads(
    (ROOT / "fixtures" / "instruments" / "scoring_design_cases.json").read_text(encoding="utf-8")
)


def specs() -> tuple[ItemScoringSpec, ItemScoringSpec]:
    return (
        ItemScoringSpec(
            item_id="p1",
            column_name="sat_p1",
            response_type="single_choice",
            response_options=(("1", 1), ("2", 2), ("3", 3), ("4", 4), ("5", 5)),
            valid_min=1,
            valid_max=5,
        ),
        ItemScoringSpec(
            item_id="p2",
            column_name="sat_p2",
            response_type="single_choice",
            response_options=(("1", 1), ("2", 2), ("3", 3), ("4", 4), ("5", 5)),
            valid_min=1,
            valid_max=5,
            reverse_scored=True,
            reverse_rule="min_plus_max_minus_value",
        ),
    )


def rule(aggregation: str = "mean") -> ScoringRuleSpec:
    return ScoringRuleSpec(
        rule_id="attention",
        item_ids=("p1", "p2"),
        aggregation=aggregation,  # type: ignore[arg-type]
        missing_policy="all_required",
    )


def case(name: str) -> dict[str, object]:
    return next(item for item in CASES["score_cases"] if item["id"] == name)


def cronbach_case(name: str) -> dict[str, object]:
    return next(item for item in CASES["cronbach_cases"] if item["id"] == name)


def test_calculates_confirmed_mean_and_reverse_coding() -> None:
    data = case("direct_and_reverse_mean")

    result = calculate_scores([data["input"]], specs(), rule())

    assert result.values == (data["expected_mean"],)
    assert result.valid_rows == 1
    assert result.missing_rows == 0


def test_missing_required_item_preserves_row_as_unscored() -> None:
    data = case("all_required_missing")

    result = calculate_scores([data["input"]], specs(), rule())

    assert result.values == (None,)
    assert result.valid_rows == 0
    assert result.missing_rows == 1


@pytest.mark.parametrize("name", ["unknown_code", "non_numeric_code"])
def test_unknown_codes_are_errors_not_missing_values(name: str) -> None:
    data = case(name)

    with pytest.raises(ScoringValidationError, match="código de respuesta desconocido"):
        calculate_scores([data["input"]], specs(), rule())


def test_calculates_sum_when_the_confirmed_rule_requires_it() -> None:
    data = case("direct_and_reverse_mean")

    result = calculate_scores([data["input"]], specs(), rule("sum"))

    assert result.values == (data["expected_sum"],)


def test_reuses_cronbach_with_original_recoded_items() -> None:
    data = cronbach_case("recoded_identical_items")

    result = calculate_cronbach_reliability(data["input_rows"], specs())

    assert result.result.metrics["alpha"] == data["expected_alpha"]
    assert result.valid_rows == data["expected_valid_rows"]
    assert result.excluded_rows == data["expected_excluded_rows"]


def test_cronbach_reports_complete_case_accounting() -> None:
    data = cronbach_case("complete_cases_only")

    result = calculate_cronbach_reliability(data["input_rows"], specs())

    assert result.result.metrics["alpha"] == data["expected_alpha"]
    assert result.valid_rows == data["expected_valid_rows"]
    assert result.excluded_rows == data["expected_excluded_rows"]


def test_cronbach_rejects_constant_scale() -> None:
    data = cronbach_case("constant_scale")

    with pytest.raises(StatisticalCalculationError, match="varianza total es cero"):
        calculate_cronbach_reliability(data["input_rows"], specs())


def test_cronbach_rejects_insufficient_complete_rows() -> None:
    data = cronbach_case("insufficient_complete_rows")

    with pytest.raises(StatisticalCalculationError, match="al menos dos filas completas"):
        calculate_cronbach_reliability(data["input_rows"], specs())


def test_missing_mapped_column_is_not_treated_as_a_missing_response() -> None:
    with pytest.raises(ScoringValidationError, match="columna vinculada ausente"):
        calculate_scores([{"sat_p1": "4"}], specs(), rule())


def test_numeric_values_outside_a_confirmed_range_are_rejected() -> None:
    numeric_item = ItemScoringSpec(
        item_id="n1",
        column_name="numeric_input",
        response_type="numeric",
        valid_min=1,
        valid_max=5,
    )
    numeric_rule = ScoringRuleSpec(
        rule_id="numeric-rule",
        item_ids=("n1",),
        aggregation="mean",
        missing_policy="all_required",
    )

    with pytest.raises(ScoringValidationError, match="valor fuera del rango confirmado"):
        calculate_scores([{"numeric_input": "6"}], (numeric_item,), numeric_rule)
