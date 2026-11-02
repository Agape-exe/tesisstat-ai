from math import isclose
from pathlib import Path

from fastapi.testclient import TestClient

from app.modules.statistics.api import create_descriptive_app
from app.modules.statistics.descriptive import (
    describe_categorical,
    describe_column,
    describe_numeric,
    profile_column,
)


def test_numeric_summary_uses_sample_statistics_and_type_7_quantiles():
    summary = describe_numeric(["1", "2", "2", "4", None])
    assert summary.valid_count == 4
    assert summary.missing_count == 1
    assert summary.mean == 2.25
    assert summary.median == 2
    assert summary.modes == [2]
    assert summary.sample_variance is not None and isclose(
        summary.sample_variance, 1.5833333333333333
    )
    assert summary.sample_standard_deviation is not None and isclose(
        summary.sample_standard_deviation, 1.2583057392117916
    )
    assert summary.quantiles == {"p0": 1, "p25": 1.75, "p50": 2, "p75": 2.5, "p100": 4}


def test_numeric_summary_handles_empty_constant_and_tied_modes():
    empty = describe_numeric([None, "", "NA"])
    assert empty.mean is None
    assert empty.quantiles is None
    constant = describe_numeric(["5", "5", "5"])
    assert constant.sample_variance == 0
    assert constant.sample_standard_deviation == 0
    tied = describe_numeric(["1", "1", "2", "2", "3"])
    assert tied.modes == [1, 2]
    assert tied.mode_tied


def test_column_classification_and_categorical_frequencies():
    assert profile_column("participant_id", ["1", "2"]).kind == "identifier"
    assert profile_column("score", ["1", "2", ""]).kind == "numeric"
    assert profile_column("group", ["A", "B"]).kind == "categorical"
    categorical = describe_categorical(["A", "B", "A", None])
    assert [(item.value, item.count, item.percentage) for item in categorical.frequencies] == [
        ("A", 2, 66.66666666666666),
        ("B", 1, 33.33333333333333),
    ]
    invalid = describe_column("post", ["14", "invalid"])
    assert invalid.kind == "categorical"


def test_descriptive_endpoints_expose_only_allowlisted_fixture_data():
    root = Path(__file__).resolve().parents[2]
    client = TestClient(create_descriptive_app(root))
    datasets = client.get("/datasets")
    assert datasets.status_code == 200
    assert [item["id"] for item in datasets.json()] == ["association", "quality_issues"]
    columns = client.get("/datasets/association/columns")
    assert columns.status_code == 200
    assert [column["kind"] for column in columns.json()] == ["identifier", "numeric", "numeric"]
    summary = client.post("/datasets/association/descriptive", json={"columns": ["study_hours"]})
    assert summary.status_code == 200
    assert summary.json()[0]["numeric"]["valid_count"] == 30
    cors = client.options(
        "/datasets/association/columns",
        headers={
            "Origin": "http://127.0.0.1:5173",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert cors.headers["access-control-allow-origin"] == "http://127.0.0.1:5173"
    quality_columns = client.get("/datasets/quality_issues/columns")
    assert [column["kind"] for column in quality_columns.json()] == [
        "identifier",
        "categorical",
        "numeric",
        "categorical",
        "numeric",
    ]
    categorical = client.post("/datasets/quality_issues/descriptive", json={"columns": ["group"]})
    assert categorical.json()[0]["categorical"]["frequencies"][0] == {
        "value": "B",
        "count": 2,
        "percentage": 50.0,
    }
    assert (
        client.post("/datasets/association/descriptive", json={"columns": ["unknown"]}).status_code
        == 422
    )
    assert client.get("/datasets/nope/columns").status_code == 404
