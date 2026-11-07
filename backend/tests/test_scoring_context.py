import json
from pathlib import Path

import pytest

from app.modules.statistics.scoring_context import (
    InstrumentContextConsumptionError,
    calculate_context_cronbach,
    calculate_context_scores,
    scoring_inputs_from_context,
)
from app.shared.instrument_context import InstrumentContext

ROOT = Path(__file__).resolve().parents[2]
CONTEXT_PAYLOAD = json.loads(
    (ROOT / "fixtures" / "instruments" / "satisfaction_confirmed.context.json").read_text(
        encoding="utf-8"
    )
)
SCORING_CASES = json.loads(
    (ROOT / "fixtures" / "instruments" / "scoring_design_cases.json").read_text(encoding="utf-8")
)


def context() -> InstrumentContext:
    return InstrumentContext.model_validate(CONTEXT_PAYLOAD)


def rule_id() -> str:
    return str(context().scoring_rules[0].scoring_rule_id)


def test_consumes_confirmed_context_without_research_services() -> None:
    inputs = scoring_inputs_from_context(context(), rule_id())

    assert inputs.rule.aggregation == "mean"
    assert [item.column_name for item in inputs.item_specs] == ["sat_p1", "sat_p2"]
    assert inputs.item_specs[1].reverse_scored is True


def test_calculates_scores_from_the_synthetic_contract_fixture() -> None:
    result = calculate_context_scores(context(), rule_id(), [{"sat_p1": "4", "sat_p2": "2"}])

    assert result.values == (4.0,)
    assert result.valid_rows == 1


def test_calculates_cronbach_from_original_recoded_items() -> None:
    cronbach_case = next(
        item for item in SCORING_CASES["cronbach_cases"] if item["id"] == "recoded_identical_items"
    )

    result = calculate_context_cronbach(context(), rule_id(), cronbach_case["input_rows"])

    assert result.result.metrics["alpha"] == 1.0
    assert result.valid_rows == 4
    assert result.excluded_rows == 0


def test_rejects_context_without_a_confirmed_mapping() -> None:
    payload = CONTEXT_PAYLOAD | {"dataset_mapping": None}

    with pytest.raises(InstrumentContextConsumptionError, match="no tiene un mapeo"):
        calculate_context_scores(
            InstrumentContext.model_validate(payload), rule_id(), [{"sat_p1": "4", "sat_p2": "2"}]
        )
