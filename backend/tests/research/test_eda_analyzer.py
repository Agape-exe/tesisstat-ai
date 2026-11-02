import io

from openpyxl import Workbook

from app.modules.research.datasets.readers import DatasetLimits
from app.modules.research.eda.analyzer import ExploratoryAnalyzer


def test_full_csv_profile():
    lines = ["id,valor,categoria,vacio"]
    lines += [f"A{i:06d},{i},NA," for i in range(22)]
    lines += ["A000000,0,NA,", "A000024,malo,N/A,"]
    report = ExploratoryAnalyzer().analyze(
        ("\n".join(lines) + "\n").encode(), "csv", DatasetLimits()
    )
    assert report["summary"]["rows"] == 24
    assert report["summary"]["duplicates"] == 1
    assert report["summary"]["missing"] == 48
    assert report["summary"]["empty_columns"] == 2
    assert report["columns"][1]["numeric_valid"] == 23
    assert report["columns"][1]["incompatible_examples"] == ["malo"]
    assert report["columns"][0]["possible_identifier"]


def test_xlsx_formula_and_zero_denominators():
    book = Workbook()
    sheet = book.active
    sheet.append(["fecha", "medida"])
    sheet.append(["01/02/2024", "=1+1"])
    sheet.append(["2024-01-02", 2])
    output = io.BytesIO()
    book.save(output)
    report = ExploratoryAnalyzer().analyze(output.getvalue(), "xlsx", DatasetLimits())
    assert report["summary"]["rows"] == 2
    assert any("fórmulas" in warning["message"] for warning in report["warnings"])
    assert any("ambiguo" in warning["message"] for warning in report["warnings"])
    empty = ExploratoryAnalyzer().analyze(b"A,B\n", "csv", DatasetLimits())
    assert empty["summary"]["missing_percentage"] == 0
    assert empty["summary"]["duplicate_percentage"] == 0
