import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.shared.instrument_context import InstrumentContext as LegacyInstrumentContext
from app.shared.instrument_contracts import InstrumentContext

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "docs" / "contracts" / "examples"


def load(name: str) -> dict[str, object]:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_confirmed_synthetic_instrument_context_is_valid() -> None:
    context = InstrumentContext.model_validate(load("instrument_confirmed_with_mapping.json"))

    assert context.status == "reviewed"
    assert context.dataset_mapping is not None
    assert context.dataset_mapping.status == "confirmed"
    assert context.scoring_rules[0].missing_policy == "all_required"


@pytest.mark.parametrize(
    "fixture, message",
    [
        (
            "instrument_confirmed_with_mapping.json",
            "confirmation.state='confirmed'",
        ),
    ],
)
def test_invalid_context_fixtures_are_rejected(fixture: str, message: str) -> None:
    payload = load(fixture)
    payload["dataset_mapping"]["confirmation"]["state"] = "pending"
    payload["dataset_mapping"]["confirmation"]["confirmed_at"] = None
    payload["dataset_mapping"]["confirmation"]["confirmer_ref"] = None
    with pytest.raises(ValidationError, match=message):
        InstrumentContext.model_validate(payload)


def test_reverse_item_without_confirmed_range_is_rejected() -> None:
    payload = load("instrument_confirmed_with_mapping.json")
    payload["items"][1]["valid_min"] = None
    payload["items"][1]["valid_max"] = None

    with pytest.raises(ValidationError, match="valid_min y valid_max"):
        InstrumentContext.model_validate(payload)


def test_confirmed_mapping_requires_every_instrument_item() -> None:
    payload = load("instrument_confirmed_with_mapping.json")
    payload["dataset_mapping"]["item_columns"].pop()

    with pytest.raises(ValidationError, match="debe cubrir todos"):
        InstrumentContext.model_validate(payload)


def test_context_schema_keeps_the_agreed_boundary() -> None:
    schema = InstrumentContext.model_json_schema()

    assert schema["properties"]["schema_version"]["const"] == "1.0.0"
    assert "dataset_mapping" in schema["properties"]
    assert "rows" not in schema["properties"]
    assert "dataset_version" not in schema["$defs"]["DatasetMapping"]["properties"]


def test_legacy_statistics_module_reexports_the_public_contract() -> None:
    assert LegacyInstrumentContext is InstrumentContext
