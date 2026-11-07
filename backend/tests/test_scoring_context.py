import json
from pathlib import Path

import pytest

from app.modules.statistics.scoring_context import (
    InstrumentContextConsumptionError,
    calculate_context_cronbach,
    calculate_context_scores,
    scoring_inputs_from_context,
)
from app.shared.instrument_contracts import InstrumentContext

ROOT = Path(__file__).resolve().parents[2]
CONTEXT_PAYLOAD = json.loads(
    (ROOT / "docs" / "contracts" / "examples" / "instrument_confirmed_with_mapping.json").read_text(
        encoding="utf-8"
    )
)


def context() -> InstrumentContext:
    return InstrumentContext.model_validate(CONTEXT_PAYLOAD)


def rule_id() -> str:
    return str(context().scoring_rules[0].scoring_rule_id)


def test_consumes_confirmed_context_without_research_services() -> None:
    inputs = scoring_inputs_from_context(context(), rule_id())

    assert inputs.rule.aggregation == "sum"
    assert [item.column_name for item in inputs.item_specs] == [
        "p1_comunicacion_directa",
        "p2_info_contradictoria",
    ]
    assert inputs.item_specs[1].reverse_scored is True


def test_calculates_scores_from_the_synthetic_contract_fixture() -> None:
    result = calculate_context_scores(
        context(),
        rule_id(),
        [{"p1_comunicacion_directa": "4", "p2_info_contradictoria": "2"}],
    )

    assert result.values == (8.0,)
    assert result.valid_rows == 1


def test_calculates_cronbach_from_original_recoded_items() -> None:
    result = calculate_context_cronbach(
        context(),
        rule_id(),
        [
            {"p1_comunicacion_directa": "1", "p2_info_contradictoria": "5"},
            {"p1_comunicacion_directa": "2", "p2_info_contradictoria": "4"},
            {"p1_comunicacion_directa": "3", "p2_info_contradictoria": "3"},
            {"p1_comunicacion_directa": "4", "p2_info_contradictoria": "2"},
        ],
    )

    assert result.result.metrics["alpha"] == 1.0
    assert result.valid_rows == 4
    assert result.excluded_rows == 0


def test_rejects_context_without_a_confirmed_mapping() -> None:
    payload = CONTEXT_PAYLOAD | {"dataset_mapping": None}

    with pytest.raises(InstrumentContextConsumptionError, match="no tiene un mapeo"):
        calculate_context_scores(
            InstrumentContext.model_validate(payload),
            rule_id(),
            [{"p1_comunicacion_directa": "4", "p2_info_contradictoria": "2"}],
        )


def test_semibounded_range_is_a_scoring_precondition_not_a_contract_error() -> None:
    payload = json.loads(json.dumps(CONTEXT_PAYLOAD))
    item = payload["items"][0]
    item.update(
        {
            "response_type": "numeric",
            "response_options": [],
            "valid_min": 0,
            "valid_max": None,
            "reverse_scored": False,
            "reverse_rule": None,
        }
    )
    public_context = InstrumentContext.model_validate(payload)

    with pytest.raises(InstrumentContextConsumptionError, match="rango semiacotado"):
        scoring_inputs_from_context(public_context, rule_id())
