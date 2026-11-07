import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.shared.instrument_context import InstrumentContext

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "fixtures" / "instruments"


def load(name: str) -> dict[str, object]:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_confirmed_synthetic_instrument_context_is_valid() -> None:
    context = InstrumentContext.model_validate(load("satisfaction_confirmed.context.json"))

    assert context.status == "reviewed"
    assert context.dataset_mapping is not None
    assert context.dataset_mapping.status == "confirmed"
    assert context.scoring_rules[0].missing_policy == "all_required"


@pytest.mark.parametrize(
    "fixture, message",
    [
        (
            "invalid_unconfirmed_mapping.context.json",
            "mapeo confirmado requiere confirmación humana",
        ),
    ],
)
def test_invalid_context_fixtures_are_rejected(fixture: str, message: str) -> None:
    with pytest.raises(ValidationError, match=message):
        InstrumentContext.model_validate(load(fixture))


def test_reverse_item_without_confirmed_range_is_rejected() -> None:
    payload = load("satisfaction_confirmed.context.json")
    payload["items"][1]["valid_min"] = None
    payload["items"][1]["valid_max"] = None

    with pytest.raises(ValidationError, match="ítem invertido requiere extremos"):
        InstrumentContext.model_validate(payload)


def test_confirmed_mapping_requires_every_instrument_item() -> None:
    payload = load("satisfaction_confirmed.context.json")
    payload["dataset_mapping"]["item_columns"].pop()

    with pytest.raises(ValidationError, match="mapeo confirmado debe vincular todos"):
        InstrumentContext.model_validate(payload)


def test_context_schema_keeps_the_agreed_boundary() -> None:
    schema = InstrumentContext.model_json_schema()

    assert schema["properties"]["schema_version"]["const"] == "1.0.0"
    assert "dataset_mapping" in schema["properties"]
    assert "rows" not in schema["properties"]
    assert "dataset_version" not in schema["$defs"]["DatasetMapping"]["properties"]
