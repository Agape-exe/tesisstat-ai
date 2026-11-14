import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from pydantic import ValidationError

from app.shared.data_workspace_v2 import WORKSPACE_MODELS
from scripts.export_contracts import schema_text
from scripts.export_workspace_examples import examples

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("model", WORKSPACE_MODELS)
def test_workspace_contracts_generated_examples_and_strictness(model):
    example = json.loads(
        (ROOT / f"contracts/v2/examples/{model.__name__}.json").read_text(encoding="utf-8")
    )
    assert example == examples()[model.__name__]
    schema = json.loads(schema_text(model, "v2"))
    Draft202012Validator(schema).validate(example)
    model.model_validate(example)
    assert (ROOT / f"contracts/v2/{model.__name__}.schema.json").read_text(
        encoding="utf-8"
    ) == schema_text(model, "v2")
    with pytest.raises(ValidationError):
        model.model_validate(example | {"owner_id": "client"})
