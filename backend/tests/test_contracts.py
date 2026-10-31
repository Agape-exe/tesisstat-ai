import csv
import json
from copy import deepcopy
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from pydantic import ValidationError

from app.shared.contracts import CONTRACT_MODELS, AnalysisPlan, AnalysisResult, ResearchPackage
from scripts.export_contracts import schema_text

ROOT = Path(__file__).resolve().parents[2]


def load(path):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


@pytest.mark.parametrize("model", CONTRACT_MODELS)
def test_examples_validate_and_schemas_are_current(model):
    path = ROOT / "contracts/v1" / f"{model.__name__}.schema.json"
    schema = json.loads(path.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    example = load(f"contracts/v1/examples/{model.__name__}.json")
    Draft202012Validator(schema).validate(example)
    assert model.model_validate(example).schema_version == "1.0.0"
    assert path.read_text(encoding="utf-8") == schema_text(model)


@pytest.mark.parametrize("model", CONTRACT_MODELS)
def test_contracts_reject_unknown_fields_and_versions(model):
    example = load(f"contracts/v1/examples/{model.__name__}.json")
    for mutation in ({"schema_version": "2.0.0"}, {"unexpected": "value"}):
        invalid = example | mutation
        with pytest.raises(ValidationError):
            model.model_validate(invalid)
        schema = json.loads(schema_text(model))
        assert not Draft202012Validator(schema).is_valid(invalid)

    del example["schema_version"]
    with pytest.raises(ValidationError):
        model.model_validate(example)


@pytest.mark.parametrize(
    "problem", ["variable_ref", "column_ref", "duplicate_variable", "duplicate_hypothesis"]
)
def test_package_rejects_broken_references(problem):
    package = deepcopy(load("fixtures/research/association.package.json"))
    if problem == "variable_ref":
        package["hypotheses"][0]["variable_ids"] = ["missing"]
    elif problem == "column_ref":
        package["variables"][0]["columns"] = ["missing"]
    elif problem == "duplicate_variable":
        package["variables"].append(package["variables"][0])
    else:
        package["hypotheses"].append(package["hypotheses"][0])
    with pytest.raises(ValidationError):
        ResearchPackage.model_validate(package)


def test_dataset_matches_research_fixture():
    package = ResearchPackage.model_validate(load("fixtures/research/association.package.json"))
    with (ROOT / package.dataset.location).open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        assert reader.fieldnames == package.dataset.columns
        assert len(list(reader)) == package.dataset.row_count


def test_invalid_alpha_and_nonfinite_metrics_are_rejected():
    plan = load("fixtures/statistics/association.plan.json")
    for value in (0, 1, -0.1):
        with pytest.raises(ValidationError):
            AnalysisPlan.model_validate(plan | {"alpha": value})
    result = load("fixtures/statistics/association.result.json")
    with pytest.raises(ValidationError):
        AnalysisResult.model_validate(result | {"metrics": [{"name": "p", "value": float("nan")}]})
