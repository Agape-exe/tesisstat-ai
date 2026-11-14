import io
from urllib.parse import quote

from fastapi.testclient import TestClient
from openpyxl import Workbook

from app.modules.research.dev_app import ResearchDevSettings, create_app

PROJECT = {
    "title": "EDA sintético",
    "university": "Universidad Demo",
    "program": "Programa Demo",
    "degree": "bachelor",
}


def setup(tmp_path):
    settings = ResearchDevSettings(
        research_db_path=tmp_path / "db.sqlite3",
        research_documents_path=tmp_path / "docs",
        research_datasets_path=tmp_path / "data",
    )
    client = TestClient(create_app(settings=settings))
    project = client.post("/api/research/projects", json=PROJECT).json()["id"]
    return client, settings, project


def upload(client, project, name, content):
    response = client.post(
        f"/api/research/projects/{project}/datasets",
        content=content,
        headers={"X-File-Name": quote(name)},
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def endpoint(project, dataset):
    return f"/api/research/projects/{project}/datasets/{dataset}/eda"


def test_csv_full_profile_cache_restart_and_delete(tmp_path):
    client, settings, project = setup(tmp_path)
    lines = ["id,valor,categoria,vacio"]
    lines += [f"A{i:06d},{i},NA," for i in range(22)]
    lines += ["A000000,0,NA,", "A000024,malo,N/A,"]
    dataset = upload(client, project, "synthetic.csv", ("\n".join(lines) + "\n").encode())
    url = endpoint(project, dataset)
    assert client.get(url).status_code == 404
    first = client.post(url)
    assert first.status_code == 200, first.text
    report = first.json()
    assert report["summary"]["rows"] == 24
    assert report["summary"]["duplicates"] == 1
    assert report["summary"]["missing"] == 48
    assert report["summary"]["empty_columns"] == 2
    assert report["columns"][1]["numeric_valid"] == 23
    assert report["columns"][1]["incompatible_examples"] == ["malo"]
    assert report["columns"][0]["possible_identifier"]
    assert client.post(url).json()["processed_at"] == report["processed_at"]
    restarted = TestClient(create_app(settings=settings))
    assert restarted.get(url).json()["summary"]["rows"] == 24
    assert restarted.post(f"/api/research/projects/{project}/datasets/{dataset}").status_code == 405
    assert (
        restarted.delete(f"/api/research/projects/{project}/datasets/{dataset}").status_code == 204
    )
    assert restarted.get(url).status_code == 404


def test_xlsx_formula_and_empty_rows(tmp_path):
    client, _, project = setup(tmp_path)
    book = Workbook()
    sheet = book.active
    sheet.append(["fecha", "medida"])
    sheet.append(["01/02/2024", "=1+1"])
    sheet.append(["2024-01-02", 2])
    output = io.BytesIO()
    book.save(output)
    dataset = upload(client, project, "synthetic.xlsx", output.getvalue())
    report = client.post(endpoint(project, dataset)).json()
    assert report["summary"]["rows"] == 2
    assert any("fórmulas" in warning["message"] for warning in report["warnings"])
    assert any("ambiguo" in warning["message"] for warning in report["warnings"])

    empty = upload(client, project, "empty.csv", b"A,B\n")
    empty_report = client.post(endpoint(project, empty)).json()
    assert empty_report["summary"]["missing_percentage"] == 0
    assert empty_report["summary"]["duplicate_percentage"] == 0


def test_other_project_hidden(tmp_path):
    client, _, project = setup(tmp_path)
    dataset = upload(client, project, "data.csv", b"A\n1\n")
    other = client.post("/api/research/projects", json=PROJECT).json()["id"]
    assert client.post(endpoint(other, dataset)).status_code == 404
