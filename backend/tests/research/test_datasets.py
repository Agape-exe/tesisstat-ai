import io
from urllib.parse import quote

import pytest
from fastapi.testclient import TestClient
from openpyxl import Workbook

from app.modules.research.datasets.readers import DatasetLimits, InvalidDataset, read_csv, read_xlsx
from app.modules.research.datasets.sqlite_repository import (
    DatasetStorageError,
    SQLiteDatasetRepository,
)
from app.modules.research.dev_app import ResearchDevSettings, create_app

PROJECT = {
    "title": "Investigación ficticia con datasets",
    "university": "Universidad de Demostración",
    "program": "Programa sintético",
    "degree": "bachelor",
}


def xlsx(sheets: dict[str, list[list[object]]]) -> bytes:
    book = Workbook()
    book.remove(book.active)
    for name, rows in sheets.items():
        sheet = book.create_sheet(name)
        for row in rows:
            sheet.append(row)
    output = io.BytesIO()
    book.save(output)
    return output.getvalue()


def client(tmp_path):
    settings = ResearchDevSettings(
        research_db_path=tmp_path / "projects.sqlite3",
        research_documents_path=tmp_path / "documents",
        research_datasets_path=tmp_path / "datasets",
    )
    app = TestClient(create_app(settings=settings))
    project_id = app.post("/api/research/projects", json=PROJECT).json()["id"]
    return app, settings, project_id


def upload(app, project_id, name, data):
    return app.post(
        f"/api/research/projects/{project_id}/datasets",
        content=data,
        headers={"X-File-Name": quote(name), "Content-Type": "application/octet-stream"},
    )


def test_csv_upload_preview_active_restart_and_cleanup(tmp_path):
    app, settings, project_id = client(tmp_path)
    first = upload(app, project_id, "datos.csv", b'\xef\xbb\xbfA;B\r\n1;"dos\nlineas"\r\n')
    assert first.status_code == 201
    first_id = first.json()["id"]
    assert first.json()["columns"] == ["A", "B"]
    assert first.json()["row_count"] == 1
    second = upload(app, project_id, "otros.csv", b"A,B\n3,4\n")
    second_id = second.json()["id"]
    assert app.post(f"/api/research/projects/{project_id}/datasets/{first_id}/activate").json()[
        "active"
    ]
    assert app.post(f"/api/research/projects/{project_id}/datasets/{second_id}/activate").json()[
        "active"
    ]
    restarted = TestClient(create_app(settings=settings))
    listing = restarted.get(f"/api/research/projects/{project_id}/datasets").json()
    assert [item["id"] for item in listing if item["active"]] == [second_id]
    preview = restarted.get(f"/api/research/projects/{project_id}/datasets/{first_id}/preview")
    assert preview.json()["rows"] == [["1", "dos\nlineas"]]
    assert len(list(settings.research_datasets_path.iterdir())) == 2
    assert (
        restarted.delete(f"/api/research/projects/{project_id}/datasets/{first_id}").status_code
        == 204
    )
    assert len(list(settings.research_datasets_path.iterdir())) == 1
    assert restarted.delete(f"/api/research/projects/{project_id}").status_code == 204
    assert list(settings.research_datasets_path.iterdir()) == []


def test_xlsx_first_sheet_and_formula_warning(tmp_path):
    app, _, project_id = client(tmp_path)
    data = xlsx({"Primera": [["A", "B"], [1, "=A2+1"]], "Segunda": [["Otro"], [99]]})
    result = upload(app, project_id, "datos.xlsx", data)
    assert result.status_code == 201, result.text
    assert result.json()["sheet"] == "Primera"
    assert result.json()["warnings"]
    preview = app.get(f"/api/research/projects/{project_id}/datasets/{result.json()['id']}/preview")
    assert preview.json()["rows"] == [["1", "=A2+1"]]


@pytest.mark.parametrize(
    ("name", "data"),
    [
        ("vacío.csv", b""),
        ("mal.txt", b"A,B\n1,2"),
        ("mal.csv", b"PK\x03\x04"),
        ("mal.xlsx", b"A,B\n1,2"),
        ("duplicado.csv", b"A,A\n1,2"),
        ("sin_cabecera.csv", b"A,\n1,2"),
        ("irregular.csv", b"A,B\n1"),
        ("latin.csv", b"A,B\n\xff,2"),
        ("grande.csv", b"A\n" + b"x" * (10 * 1024 * 1024)),
        ("inválido.xlsx", b"PK\x03\x04garbage"),
        ("macro.xlsm", xlsx({"Hoja": [["A"], [1]]})),
    ],
)
def test_invalid_uploads(tmp_path, name, data):
    app, _, project_id = client(tmp_path)
    assert upload(app, project_id, name, data).status_code == 422


def test_limits_and_preview():
    limits = DatasetLimits(max_rows=2, max_columns=2, preview_rows=1)
    assert read_csv(b"A,B\n1,2\n3,4", limits).rows == [["1", "2"]]
    with pytest.raises(InvalidDataset):
        read_csv(b"A,B\n1,2\n3,4\n5,6", limits)
    with pytest.raises(InvalidDataset):
        read_csv(b"A,B,C\n1,2,3", limits)
    with pytest.raises(InvalidDataset):
        read_xlsx(xlsx({"Hoja": [["A", "B", "C"], [1, 2, 3]]}), limits)
    with pytest.raises(InvalidDataset):
        read_xlsx(xlsx({"Hoja": [["A"], [1], [2], [3]]}), limits)
    with pytest.raises(InvalidDataset):
        read_xlsx(xlsx({"Hoja": [["A"], [1]]}), DatasetLimits(max_zip_bytes=100))


def test_other_project_is_hidden(tmp_path):
    app, _, project_id = client(tmp_path)
    other_id = app.post("/api/research/projects", json=PROJECT).json()["id"]
    dataset_id = upload(app, project_id, "datos.csv", b"A\n1\n").json()["id"]
    base = f"/api/research/projects/{other_id}/datasets/{dataset_id}"
    assert app.get(base).status_code == 404
    assert app.get(base + "/preview").status_code == 404
    assert app.post(base + "/activate").status_code == 404
    assert app.delete(base).status_code == 404
    assert app.get(f"/api/research/projects/{project_id}/datasets/{dataset_id}").status_code == 200


def test_storage_error_is_reported_without_exposing_paths(tmp_path, monkeypatch):
    app, _, project_id = client(tmp_path)

    def fail(*_args):
        raise DatasetStorageError

    monkeypatch.setattr(SQLiteDatasetRepository, "add", fail)
    response = upload(app, project_id, "datos.csv", b"A\n1\n")
    assert response.status_code == 503
    assert "path" not in response.text.lower()
