import csv
import io
from urllib.parse import quote

import pytest
from fastapi.testclient import TestClient
from openpyxl import Workbook

from app.modules.research.datasets.readers import DatasetLimits
from app.modules.research.dev_app import ResearchDevSettings, create_app
from app.modules.research.preparation.engine import InvalidPlan, transform
from app.modules.research.preparation.models import Plan


def run(data: bytes, operations: list[dict]) -> dict:
    return transform(data, "csv", Plan.model_validate({"operations": operations}), DatasetLimits())


@pytest.mark.parametrize(
    ("operation", "expected_rows", "expected_columns"),
    [
        ({"type": "drop_duplicates"}, 2, ["id", "name", "value"]),
        (
            {"type": "drop_missing", "columns": ["value"], "missing_markers": ["NA"]},
            2,
            ["id", "name", "value"],
        ),
        (
            {"type": "replace_missing", "column": "value", "missing_markers": ["NA"], "value": "0"},
            3,
            ["id", "name", "value"],
        ),
        ({"type": "drop_columns", "columns": ["name"]}, 3, ["id", "value"]),
        (
            {"type": "rename_column", "column": "name", "new_name": "label"},
            3,
            ["id", "label", "value"],
        ),
        ({"type": "trim", "columns": ["name"]}, 3, ["id", "name", "value"]),
    ],
)
def test_each_operation(operation, expected_rows, expected_columns):
    result = run(b"id,name,value\n1, Ana ,2\n1, Ana ,2\n2,Bob,NA\n", [operation])
    assert len(result["rows"]) == expected_rows
    assert result["columns"] == expected_columns


def test_order_numeric_and_original_representation():
    result = run(
        b"id,value\n1,001.50\n2,NA\n",
        [
            {"type": "rename_column", "column": "value", "new_name": "score"},
            {"type": "replace_missing", "column": "score", "value": "3", "missing_markers": ["NA"]},
            {"type": "to_numeric", "column": "score"},
        ],
    )
    assert result["rows"] == [["1", "1.50"], ["2", "3"]]
    assert result["warnings"]
    with pytest.raises(InvalidPlan):
        run(b"code\nA1\n", [{"type": "to_numeric", "column": "code"}])


def test_csv_special_values_and_formula_rejection():
    result = run(b'head,text\n1,"line\n""quoted"""\n', [{"type": "trim", "columns": ["head"]}])
    assert list(csv.reader(io.StringIO(result["data"].decode()))) == [
        ["head", "text"],
        ["1", 'line\n"quoted"'],
    ]
    with pytest.raises(InvalidPlan):
        run(b"head\n=1+1\n", [{"type": "drop_duplicates"}])


def test_empty_dataset_invalid_column_and_duplicate_rename():
    assert run(b"head\n", [{"type": "drop_duplicates"}])["rows"] == []
    with pytest.raises(InvalidPlan):
        run(b"head\n1\n", [{"type": "trim", "columns": ["other"]}])
    with pytest.raises(InvalidPlan):
        run(b"a,b\n1,2\n", [{"type": "rename_column", "column": "a", "new_name": "b"}])
    with pytest.raises(InvalidPlan):
        run(b"a\n1\n", [{"type": "drop_columns", "columns": ["a"]}])


def test_xlsx_formula_is_not_evaluated():
    book = Workbook()
    sheet = book.active
    sheet.append(["value"])
    sheet.append(["=1+1"])
    output = io.BytesIO()
    book.save(output)
    with pytest.raises(InvalidPlan):
        transform(
            output.getvalue(),
            "xlsx",
            Plan.model_validate({"operations": [{"type": "drop_duplicates"}]}),
            DatasetLimits(),
        )


def test_preview_apply_history_retry_and_source_protection(tmp_path):
    settings = ResearchDevSettings(
        research_db_path=tmp_path / "research.sqlite3",
        research_documents_path=tmp_path / "documents",
        research_datasets_path=tmp_path / "datasets",
    )
    app = TestClient(create_app(settings=settings))
    project = app.post(
        "/api/research/projects",
        json={
            "title": "Datos sintéticos",
            "university": "Prueba",
            "program": "Prueba",
            "degree": "bachelor",
        },
    ).json()["id"]
    original = b"id,value\n1,A\n1,A\n2,B\n"
    base = f"/api/research/projects/{project}/datasets"
    source = app.post(base, content=original, headers={"X-File-Name": quote("source.csv")}).json()[
        "id"
    ]
    path = f"{base}/{source}"
    plan = {"operations": [{"type": "drop_duplicates"}]}
    before = list(settings.research_datasets_path.iterdir())
    preview = app.post(f"{path}/preparation/preview", json=plan).json()
    assert preview["rows_removed"] == 1
    assert list(settings.research_datasets_path.iterdir()) == before
    payload = {
        "plan": plan,
        "preview_id": preview["preview_id"],
        "plan_hash": preview["plan_hash"],
        "confirm": True,
    }
    assert (
        app.post(
            f"{path}/preparation/apply",
            json={**payload, "plan": {"operations": [{"type": "trim", "columns": ["id"]}]}},
        ).status_code
        == 409
    )
    first = app.post(f"{path}/preparation/apply", json=payload)
    assert first.status_code == 201, first.text
    result_id = first.json()["result_id"]
    assert app.post(f"{path}/preparation/apply", json=payload).json()["result_id"] == result_id
    assert len(app.get(f"{path}/preparations").json()) == 1
    assert app.get(f"{base}/{result_id}").json()["source_dataset_id"] == source
    assert app.get(f"{base}/{result_id}").json()["active"] is False
    assert app.post(f"{path}/eda").json()["dataset_id"] == source
    assert app.get(f"{base}/{result_id}/eda").status_code == 404
    assert app.post(f"{base}/{result_id}/eda").json()["dataset_id"] == result_id
    assert app.delete(path).status_code == 409
    assert (settings.research_datasets_path / source.replace("-", "")).read_bytes() == original
    second_preview = app.post(f"{path}/preparation/preview", json=plan).json()
    source_path = settings.research_datasets_path / source.replace("-", "")
    source_path.write_bytes(b"id,value\n9,Z\n")
    conflict = app.post(
        f"{path}/preparation/apply",
        json={
            "plan": plan,
            "preview_id": second_preview["preview_id"],
            "plan_hash": second_preview["plan_hash"],
            "confirm": True,
        },
    )
    assert conflict.status_code == 409
    source_path.write_bytes(original)
    assert app.post(f"{base}/{result_id}/activate").json()["active"]
    assert app.delete(f"{base}/{result_id}").status_code == 204
    assert app.delete(path).status_code == 204
