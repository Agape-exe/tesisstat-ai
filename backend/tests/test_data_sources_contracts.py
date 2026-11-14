import hashlib
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from pydantic import ValidationError

from app.modules.research.datasets.readers import DatasetLimits
from app.modules.research.sources.readers import Extracted, WorkbookLimits, inventory
from app.shared.analysis_v2 import canonical_hash
from app.shared.data_sources_v2 import DATA_SOURCE_MODELS
from scripts.export_contracts import schema_text
from scripts.export_source_examples import CSV, examples

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("model", DATA_SOURCE_MODELS)
def test_c3_schemas_and_examples_are_reproducible_strict_and_generated(model):
    example = json.loads(
        (ROOT / f"contracts/v2/examples/{model.__name__}.json").read_text(encoding="utf-8")
    )
    assert example == examples()[model.__name__]
    schema = json.loads(schema_text(model, "v2"))
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(example)
    model.model_validate(example)
    assert (ROOT / f"contracts/v2/{model.__name__}.schema.json").read_text(
        encoding="utf-8"
    ) == schema_text(model, "v2")
    with pytest.raises(ValidationError):
        model.model_validate(example | {"owner_id": "client"})


def test_c3_fixture_matches_original_full_extraction_hashes_and_references():
    payloads = examples()
    source, sheet, table, context = [
        payloads[name]
        for name in ("SourceFileV2", "SourceSheetV2", "ImportedTableV2", "TableContextV2")
    ]
    assert (ROOT / "contracts/v2/examples/data-sources.synthetic.csv").read_bytes() == CSV
    assert source["hash"] == table["original_hash"] == hashlib.sha256(CSV).hexdigest()
    raw = inventory(CSV, "csv", DatasetLimits(), WorkbookLimits())[0]
    extracted = Extracted(raw.rows[0], raw.rows[1:], "A1:B4", 1, [])
    assert extracted.hash == table["content_hash"]
    assert len(extracted.rows) == table["row_count"] == 3
    assert source["id"] == sheet["file_id"] == table["file_id"]
    assert sheet["id"] == table["sheet_id"] and sheet["table_id"] == table["id"]
    assert context["table_id"] == table["id"]
    assert sheet["hash"] == canonical_hash(sheet)
    assert context["hash"] == canonical_hash(context)
