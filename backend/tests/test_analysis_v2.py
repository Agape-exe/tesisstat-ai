import csv
import json
from copy import deepcopy
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from pydantic import ValidationError

from app.shared.analysis_v2 import (
    V2_CONTRACT_MODELS,
    AnalysisIntentV2,
    AnalysisSnapshotV2,
    Fact,
    ProjectContextV2,
    Provenance,
    canonical_hash,
)
from scripts.export_contracts import schema_text
from scripts.export_v2_examples import examples

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "contracts/v2/examples"


@pytest.mark.parametrize("model", V2_CONTRACT_MODELS)
def test_v2_examples_are_reproducible_valid_and_schemas_current(model):
    example = json.loads((OUTPUT / f"{model.__name__}.json").read_text(encoding="utf-8"))
    assert example == examples()[model.__name__]
    schema = json.loads(schema_text(model, "v2"))
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(example)
    assert model.model_validate(example).schema_version == "2.0.0"
    assert (ROOT / f"contracts/v2/{model.__name__}.schema.json").read_text(
        encoding="utf-8"
    ) == schema_text(model, "v2")
    for change in ({"schema_version": "1.0.0"}, {"schema_version": "3.0.0"}, {"unexpected": True}):
        with pytest.raises(ValidationError):
            model.model_validate(example | change)


def test_snapshot_fixture_refs_have_real_matching_sources_and_no_hypothesis():
    payloads = examples()
    snapshot = AnalysisSnapshotV2.model_validate(payloads["AnalysisSnapshotV2"])
    assert snapshot.intent.hypothesis_id is None
    sources = payloads["sources"] | {
        "context": payloads["ProjectContextV2"],
        "intent": payloads["AnalysisIntentV2"],
    }
    for ref in snapshot.source_refs:
        source = sources[ref.kind]
        assert source["project_id"] == snapshot.project_id
        assert source.get("id", source["project_id"]) == ref.id
        assert source["revision"] == ref.revision
        assert canonical_hash(source) == ref.hash
    with (OUTPUT / "sales.synthetic.csv").open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == sources["dataset"]["row_count"] == sources["profile"]["valid_count"]


@pytest.mark.parametrize(
    "problem", ["project", "intent_ref", "hash", "fingerprint", "variable", "kind", "unconfirmed"]
)
def test_snapshot_rejects_incoherent_references(problem):
    snapshot = deepcopy(examples()["AnalysisSnapshotV2"])
    if problem == "project":
        snapshot["project_id"] = "other"
    elif problem == "intent_ref":
        snapshot["intent_ref"]["revision"] = 2
    elif problem == "hash":
        snapshot["intent"]["alpha"] = 0.1
    elif problem == "fingerprint":
        snapshot["source_fingerprint"] = "a" * 64
    elif problem == "variable":
        snapshot["variables"][0]["id"] = "missing"
    elif problem == "kind":
        snapshot["dataset_ref"]["kind"] = "document"
    else:
        snapshot["confirmed_facts"]["/main_objective"]["confirmation"] = None
    with pytest.raises(ValidationError):
        AnalysisSnapshotV2.model_validate(snapshot)


def test_fact_provenance_unknown_and_nonfinite_values_are_rejected():
    with pytest.raises(ValidationError):
        Fact(
            value="unknown",
            confirmation={
                "actor_ref": "local",
                "confirmed_at": "2026-11-09T12:00:00Z",
                "revision": 1,
            },
        )
    for provenance in (
        {"kind": "document"},
        {"kind": "derived"},
        {"kind": "unknown", "source_refs": [examples()["AnalysisSnapshotV2"]["dataset_ref"]]},
    ):
        with pytest.raises(ValidationError):
            Provenance.model_validate(provenance)
    intent = examples()["AnalysisIntentV2"]
    for alpha in (float("nan"), float("inf"), 0, 1):
        with pytest.raises(ValidationError):
            AnalysisIntentV2.model_validate(intent | {"alpha": alpha})
    with pytest.raises(ValidationError):
        ProjectContextV2.model_validate(examples()["ProjectContextV2"] | {"revision": 0})


def test_hash_excludes_confirmations_dates_but_preserves_nested_source_hashes():
    context = examples()["ProjectContextV2"]
    changed = deepcopy(context)
    changed["updated_at"] = "2026-11-10T12:00:00Z"
    changed["main_objective"]["confirmation"] = None
    assert canonical_hash(context) == canonical_hash(changed)
    changed["main_objective"]["value"] = "Otro objetivo"
    assert canonical_hash(context) != canonical_hash(changed)
    a = {"source_refs": [{"hash": "a" * 64}]}
    b = {"source_refs": [{"hash": "b" * 64}]}
    assert canonical_hash(a) != canonical_hash(b)
