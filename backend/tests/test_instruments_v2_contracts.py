import json
from copy import deepcopy
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from pydantic import ValidationError

from app.shared.analysis_v2 import canonical_hash
from app.shared.instruments_v2 import INSTRUMENT_MODELS, InstrumentStructureV2, ScoreRecordV2
from scripts.export_contracts import schema_text
from tests.research.test_instruments_v2 import structure

ROOT = Path(__file__).resolve().parents[2]


def test_existing_score_receipt_retains_its_serialization_and_hash():
    value = json.loads((ROOT / "contracts/v2/examples/ScoreRecordV2.json").read_text("utf-8"))
    assert "instrument_id" not in value
    score = ScoreRecordV2.model_validate(value)
    assert score.instrument_id is None
    assert score.model_dump(mode="json") == value
    assert canonical_hash(score) == canonical_hash(value)


@pytest.mark.parametrize("model", INSTRUMENT_MODELS)
def test_real_c6_examples_and_generated_schemas(model):
    value = json.loads((ROOT / f"contracts/v2/examples/{model.__name__}.json").read_text("utf-8"))
    model.model_validate(value)
    schema = json.loads(schema_text(model, "v2"))
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(value)
    assert (ROOT / f"contracts/v2/{model.__name__}.schema.json").read_text("utf-8") == schema_text(
        model, "v2"
    )
    with pytest.raises(ValidationError):
        model.model_validate(value | {"client_actor": "fabricated"})


@pytest.mark.parametrize(
    "problem", ["ids", "hierarchy", "rule", "codes", "finite", "bounds", "reverse"]
)
def test_structural_invariants(problem):
    s = deepcopy(structure())
    if problem == "ids":
        s["items"][1]["item_id"] = s["items"][0]["item_id"]
    elif problem == "hierarchy":
        s["items"][0]["dimension_id"] = s["items"][0]["item_id"]
    elif problem == "rule":
        s["scoring_rules"][0]["item_ids"] *= 2
    elif problem == "codes":
        s["items"][0].update(
            response_type="single_choice",
            response_options=[
                {"code": "x", "label": "Uno", "numeric_value": 1},
                {"code": "x", "label": "Dos", "numeric_value": 2},
            ],
        )
    elif problem == "finite":
        s["items"][0]["valid_max"] = float("inf")
    elif problem == "bounds":
        s["items"][0]["valid_min"] = 6
    else:
        s["items"][1]["reverse_rule"] = None
    with pytest.raises(ValidationError):
        InstrumentStructureV2.model_validate(s)
