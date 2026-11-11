import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from pydantic import ValidationError

from app.orchestration.analysis_v2_service import token
from app.shared.analysis_v2 import AnalysisSnapshotV2
from app.shared.plans_v2 import ANALYSIS_MODELS
from scripts.export_contracts import schema_text

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("model", ANALYSIS_MODELS)
def test_c5_real_fixtures_and_generated_schemas(model):
    value = json.loads(
        (ROOT / f"contracts/v2/examples/{model.__name__}.json").read_text(encoding="utf-8")
    )
    model.model_validate(value)
    schema = json.loads(schema_text(model, "v2"))
    Draft202012Validator(schema).validate(value)
    assert (ROOT / f"contracts/v2/{model.__name__}.schema.json").read_text(
        encoding="utf-8"
    ) == schema_text(model, "v2")
    with pytest.raises(ValidationError):
        model.model_validate({**value, "schema_version": "3.0.0"})


def test_proposal_token_covers_exact_snapshot_and_confirmations():
    from app.shared.plans_v2 import AnalysisPlanV2

    plan = AnalysisPlanV2.model_validate_json(
        (ROOT / "contracts/v2/examples/AnalysisPlanV2.json").read_text(encoding="utf-8")
    )
    snapshot = AnalysisSnapshotV2.model_validate_json(
        (ROOT / "contracts/v2/examples/AnalysisSnapshotS04B.json").read_text(encoding="utf-8")
    )
    assert token(plan, snapshot) == plan.proposal_token
    snapshot.intent.confirmation.actor_ref = "tampered"
    assert token(plan, snapshot) != plan.proposal_token
