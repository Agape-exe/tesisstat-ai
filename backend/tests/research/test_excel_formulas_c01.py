"""Synthetic-only references, independently calculated with Fraction/manual arithmetic."""

import io
import json
import zipfile
from fractions import Fraction
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest
from fastapi.testclient import TestClient
from openpyxl import Workbook
from openpyxl.worksheet.formula import ArrayFormula
from openpyxl.worksheet.table import Table

from app.modules.research.datasets.readers import DatasetLimits
from app.modules.research.dev_app import create_app
from app.modules.research.sources.readers import WorkbookLimits, detect, extract, inventory
from app.shared.analysis_v2 import canonical_hash
from app.shared.data_workspace_v2 import TableProfileV2, VariableDictionaryV2
from tests.research.test_analysis_workflow_v2 import approve, execute, proposal
from tests.research.test_diagnostics_v2 import diagnose
from tests.research.test_sources_v2 import setup as setup


def save(book):
    stream = io.BytesIO()
    book.save(stream)
    book.close()
    return stream.getvalue()


def synthetic_book():
    book = Workbook()
    first = book.active
    first.title = "Huerto inicial"
    later = book.create_sheet("Control d'agua")
    first.append(
        [
            "parcela",
            "altura uno",
            "altura dos",
            "altura tres",
            None,
            "Media inicial",
            "Media control",
            "Diferencia",
        ]
    )
    later.append(["parcela", "altura uno", "altura dos", "altura tres", None, "Media"])
    for row in range(2, 25):
        first.append(
            [
                f"{row - 1:03}",
                row,
                row + 1,
                row + 2,
                None,
                "=AVERAGE(Cultivo[[#This Row],[altura uno]:[altura tres]])",
                "=AVERAGE(Riego[[#This Row],[altura uno]:[altura tres]])",
                f"=G{row}-F{row}",
            ]
        )
        later.append([f"{row - 1:03}", row + 3, row + 5, row + 7, None, f"=AVERAGE(B{row}:D{row})"])
    first.add_table(Table(displayName="Cultivo", ref="A1:D24"))
    later.add_table(Table(displayName="Riego", ref="A1:D24"))
    return save(book)


def raw(data):
    return inventory(data, "xlsx", DatasetLimits(), WorkbookLimits())


def cached(data, value):
    out = io.BytesIO()
    ns = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
    with zipfile.ZipFile(io.BytesIO(data)) as src, zipfile.ZipFile(out, "w") as dst:
        for item in src.infolist():
            content = src.read(item.filename)
            if item.filename.startswith("xl/worksheets/sheet") and item.filename.endswith(".xml"):
                root = ET.fromstring(content)
                for cell in root.iter(ns + "c"):
                    if cell.find(ns + "f") is not None:
                        result = cell.find(ns + "v")
                        if result is not None:
                            cell.remove(result)
                        if value is not None:
                            ET.SubElement(cell, ns + "v").text = value
                content = ET.tostring(root)
            dst.writestr(item, content)
    return out.getvalue()


@pytest.mark.parametrize("cache", [None, "999999"])
def test_every_formula_structured_cross_sheet_and_separators_with_untrusted_cache(cache):
    sheets = raw(cached(synthetic_book(), cache))
    assert len(sheets) == 2
    for index, sheet in enumerate(sheets):
        table, reason = detect(sheet, DatasetLimits())
        assert table, reason
        assert len(table.rows) == 23
        assert table.omitted_columns == ["E"]
        assert table.source_columns == (
            ["A", "B", "C", "D", "F", "G", "H"] if index == 0 else ["A", "B", "C", "D", "F"]
        )
        for r, values in enumerate(table.rows, 2):
            # Independent closed-form expectations, not the production parser or cache.
            expected = (
                [Fraction(3 * r + 3, 3), Fraction(3 * r + 15, 3), Fraction(4)]
                if index == 0
                else [Fraction(3 * r + 15, 3)]
            )
            assert values[0] == f"{r - 1:03}"
            assert [float(v) for v in values[4:]] == [float(v) for v in expected]
        assert all(f["status"] == "calculated" for f in table.calculation["formulas"])
        assert len(table.calculation["formulas"]) == (69 if index == 0 else 23)
        assert table.calculation["cell_types"][0][0:4] == ["text", "number", "number", "number"]


def test_empty_columns_keep_rows_missing_values_and_missing_header_requires_clarification():
    book = Workbook()
    sheet = book.active
    sheet.append(["muestra", "medida", None, "resultado"])
    sheet.append(["001", 0, None, "=B2+1"])
    sheet.append([None, None, None, None])
    sheet.append(["003", None, None, "=B4+1"])
    table = extract(raw(save(book))[0], 1, "A1:D4", DatasetLimits())
    assert table.rows == [["001", "0", "1.0"], [None, None, None], ["003", None, "#C01!VALUE"]]
    book = Workbook()
    book.active.append(["id", None, "importe"])
    book.active.append(["A", "dato sin título", 6])
    table, explanation = detect(raw(save(book))[0], DatasetLimits())
    assert table is None and "datos sin encabezado" in explanation


@pytest.mark.parametrize(
    "formula,code",
    [
        ("=IF(B2>0,1,0)", "UNSUPPORTED"),
        ("=1/0", "DIV_ZERO"),
        ("='No existe'!A2", "REFERENCE"),
        ("=[otro.xlsx]Hoja!A2", "UNSUPPORTED"),
        ('=WEBSERVICE("https://example.invalid")', "UNSUPPORTED"),
        ("=B2^2", "UNSUPPORTED"),
        ("=SUM(B3:B4)", "NO_NUMBERS"),
        ("=1E308*1E308", "NON_FINITE"),
        ("=SUM(B2:XFD1048576)", "LIMIT"),
    ],
)
def test_errors_never_use_zero_or_cache(formula, code):
    book = Workbook()
    book.active.append(["id", "base", "estimación"])
    book.active.append(["X", 3, formula])
    sheet = raw(cached(save(book), "123"))[0]
    assert sheet.formula_results[(2, 3)]["error"] == code
    assert sheet.rows[1][2] == "#C01!" + code


def test_a1_references_quoted_sheets_absolute_cells_cycles_and_text_types():
    book = Workbook()
    first = book.active
    first.title = "Ventas"
    other = book.create_sheet("Otra d'área")
    first.append(["id", "importe", "estimación"])
    first.append(["001", 4, "=('Otra d''área'!$B$2 + B2)*2/3"])
    first.append(["002", 0, "=C4"])
    first.append(["003", 2, "='Otra d''área'!C3"])
    other.append(["id", "importe", "estimación"])
    other.append(["A", 8, "=AVERAGE(Ventas!B2:B4)"])
    other.append(["B", "001", "=Ventas!C3"])
    other.append(["C", None, "=B3+1"])
    other.append(
        ["D", 1, "=SUM(Ventas!B2:B4,1,3)+MIN(Ventas!B2:B4)+MAX(Ventas!B2:B4)+COUNT(Ventas!B2:B4)"]
    )
    other.append(["E", 1, "=-2+3*4/2"])
    a, b = raw(save(book))
    assert a.rows[1][2] == "8.0"
    assert b.rows[1][2] == "2.0"
    assert a.formula_results[(3, 3)]["error"] == "CYCLE"
    assert a.formula_results[(4, 3)]["error"] == "CYCLE"
    assert b.formula_results[(3, 3)]["error"] == "CYCLE"
    assert b.formula_results[(4, 3)]["error"] == "VALUE"  # numeric text is not a number
    assert b.rows[4][2] == "17.0"  # (4+0+2+1+3) + 0 + 4 + 3
    assert b.rows[5][2] == "4.0"  # unary and multiplication/division before addition


def test_array_formulas_are_explicitly_unsupported_and_source_errors_remain_errors():
    book = Workbook()
    sheet = book.active
    sheet.append(["registro", "medida", "estimación"])
    sheet.append(["R01", "#DIV/0!", "=B2+1"])
    sheet.append(["R02", 2, ArrayFormula(ref="C3:C4", text="=SUM(B2:B3)")])
    data = save(book)
    first, second = raw(data)[0], raw(data)[0]
    assert first.rows == second.rows
    assert first.rows[1][1] == "#C01!SOURCE_ERROR"
    assert first.formula_results[(2, 3)]["error"] == "SOURCE_ERROR"
    assert first.formula_results[(3, 3)]["formula"] == "=SUM(B2:B3)"
    assert first.formula_results[(3, 3)]["error"] == "UNSUPPORTED"


def test_excel_text_that_starts_with_equals_remains_text_in_profile(setup):
    client, root, _, _ = setup
    book = Workbook()
    sheet = book.active
    sheet.append(["parcela", "texto literal", "cálculo"])
    sheet.append(["001", "=1+2", "=1+2"])
    sheet["B2"].data_type = "s"
    file = client.post(
        root + "/files", content=save(book), headers={"X-File-Name": "tipos.xlsx"}
    ).json()
    table_id = file["sheets"][0]["table_id"]
    _, _, profile = review(client, root, table_id)
    assert [c["formula_count"] for c in profile["columns"]] == [0, 0, 1]
    assert profile["columns"][1]["storage_type"] == "string"
    audit = client.get(root + f"/tables/{table_id}/calculation").json()
    assert audit["cell_types"] == [["text", "text", "formula"]]


def review(client, root, table_id):
    dataset = next(d for d in client.get(root + "/data-tables").json() if d["id"] == table_id)
    url = root + f"/data-tables/{table_id}"
    dictionary = client.get(url + "/dictionary").json()
    changes, fields = {}, []
    for v in dictionary["variables"]:
        is_id = v["name"]["value"] == "parcela"
        changes[v["id"]] = {
            "measurement_scale": "nominal" if is_id else "ratio",
            "identifier_confirmed": is_id,
        }
        fields += [
            f"/variables/{v['id']}/measurement_scale",
            f"/variables/{v['id']}/identifier_confirmed",
        ]
    response = client.patch(
        url + "/dictionary",
        json={
            "expected_revision": 0,
            "dataset_revision": 1,
            "dataset_hash": dataset["hash"],
            "changes": changes,
            "confirm_fields": fields,
        },
    )
    assert response.status_code == 200, response.text
    profile = client.post(
        url + "/profile",
        json={"dataset_revision": 1, "dataset_hash": dataset["hash"], "confirm": True},
    )
    assert profile.status_code == 201, profile.text
    return dataset, response.json(), profile.json()


def descriptive_intent(client, root, dataset, dictionary, names):
    response = client.post(
        root + "/intents",
        json={
            "expected_revision": 0,
            "confirm": True,
            "changes": {
                "question": "Describir medidas del estudio",
                "kind": "descriptive",
                "estimand": "summary",
                "dataset_id": dataset["id"],
                "variable_ids": [
                    v["id"] for v in dictionary["variables"] if v["name"]["value"] in names
                ],
            },
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_preview_profile_diagnostics_analysis_restart_and_explicit_reimport(setup):
    client, root, settings, service = setup
    data = synthetic_book()
    response = client.post(root + "/files", content=data, headers={"X-File-Name": "huerto.xlsx"})
    assert response.status_code == 201, response.text
    source = response.json()
    table_id = source["sheets"][0]["table_id"]
    dataset, dictionary, profile = review(client, root, table_id)
    assert profile["formula_policy"] == "calculated-subset-cache-ignored"
    assert [c["formula_count"] for c in profile["columns"]][-3:] == [23, 23, 23]
    assert Fraction(profile["columns"][-1]["numeric_summary"]["mean"]) == 4
    intent = descriptive_intent(
        client, root, dataset, dictionary, ["Media inicial", "Media control", "Diferencia"]
    )
    assert (
        diagnose(client, root, intent, ["complete_cases"]).json()["profile"]["complete_case_count"]
        == 23
    )
    plan = proposal(client, root, intent)
    assert plan["technique"] == "descriptive_summary", plan
    approve(client, root, plan)
    result = execute(client, root, plan).json()
    assert result["status"] == "completed", result
    assert result["case_counts"]["used"] == 23
    urls = [
        f"/tables/{table_id}/preview",
        f"/tables/{table_id}/calculation",
        f"/analysis/results/{result['id']}",
    ]
    before = [client.get(root + url).json() for url in urls]
    with TestClient(create_app(settings=settings)) as restarted:
        assert [restarted.get(root + url).json() for url in urls] == before
    new = client.post(root + f"/files/{source['id']}/reimport")
    assert new.status_code == 201, new.text
    new = new.json()
    assert new["hash"] == source["hash"] and new["reimported_from"] == source["id"]
    assert new["sheets"][0]["table_id"] != table_id
    assert (
        client.get(root + f"/data-tables/{new['sheets'][0]['table_id']}/dictionary").json()[
            "revision"
        ]
        == 0
    )
    assert client.get(root + urls[-1]).json() == before[-1]
    assert service.read_table(source["project_id"], table_id)[0].content_hash == dataset["hash"]


def test_formula_error_column_is_not_ready_even_when_declared_missing(setup):
    client, root, _, _ = setup
    book = Workbook()
    book.active.append(["parcela", "respuesta"])
    book.active.append(["001", "=UNKNOWN(3)"])
    book.active.append(["002", "=UNKNOWN(5)"])
    file = client.post(
        root + "/files", content=save(book), headers={"X-File-Name": "errores.xlsx"}
    ).json()
    table_id = file["sheets"][0]["table_id"]
    dataset, dictionary, profile = review(client, root, table_id)
    assert profile["columns"][1]["numeric_summary"] is None
    assert "no está lista" in " ".join(profile["columns"][1]["warnings"])
    variable_id = dictionary["variables"][1]["id"]
    response = client.patch(
        root + f"/data-tables/{table_id}/dictionary",
        json={
            "expected_revision": dictionary["revision"],
            "dataset_revision": 1,
            "dataset_hash": dataset["hash"],
            "changes": {variable_id: {"missing_markers": ["#C01!UNSUPPORTED"]}},
            "confirm_fields": [],
        },
    )
    assert response.status_code == 200
    dictionary = response.json()
    response = client.post(
        root + f"/data-tables/{table_id}/profile",
        json={
            "dataset_revision": 1,
            "dataset_hash": dataset["hash"],
            "confirm": True,
        },
    )
    assert response.status_code == 201
    intent = descriptive_intent(client, root, dataset, dictionary, ["respuesta"])
    response = diagnose(client, root, intent, ["complete_cases"])
    assert response.status_code == 422 and "sin valor fiable" in response.json()["error"]["message"]
    response = client.post(
        root + "/analysis/plans",
        json={
            "intent_id": intent["id"],
            "intent_revision": intent["revision"],
            "dataset_id": table_id,
            "dataset_revision": 1,
            "diagnostic_ids": [],
        },
    )
    assert response.status_code == 201
    assert response.json()["status"] == "needs_clarification"
    assert response.json()["technique"] is None


@pytest.mark.parametrize(
    "name,model",
    [("VariableDictionaryV2", VariableDictionaryV2), ("TableProfileV2", TableProfileV2)],
)
def test_pre_c01_persisted_hashes_do_not_change(name, model):
    payload = json.loads(
        (Path(__file__).resolve().parents[3] / f"contracts/v2/examples/{name}.json").read_text(
            encoding="utf8"
        )
    )
    assert canonical_hash(model.model_validate(payload)) == canonical_hash(payload)
