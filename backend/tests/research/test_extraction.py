"""Only generated, fictional files are used in extraction tests."""

import io
import sqlite3
import zipfile
from uuid import uuid4

from docx import Document as WordDocument
from fastapi.testclient import TestClient
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from app.modules.research.dev_app import ResearchDevSettings, create_app

PROJECT = {
    "title": "Estudio sintético",
    "university": "Universidad Ficticia",
    "program": "Programa de prueba",
    "degree": "bachelor",
}


def pdf(text: str = "", *, encrypted: bool = False, pages: int = 1) -> bytes:
    writer = PdfWriter()
    for _ in range(pages):
        page = writer.add_blank_page(width=300, height=300)
        if text:
            font = DictionaryObject(
                {
                    NameObject("/Type"): NameObject("/Font"),
                    NameObject("/Subtype"): NameObject("/Type1"),
                    NameObject("/BaseFont"): NameObject("/Helvetica"),
                }
            )
            page[NameObject("/Resources")] = DictionaryObject(
                {
                    NameObject("/Font"): DictionaryObject(
                        {NameObject("/F1"): writer._add_object(font)}
                    )
                }
            )
            stream = DecodedStreamObject()
            stream.set_data(f"BT /F1 12 Tf 30 250 Td ({text}) Tj ET".encode())
            page[NameObject("/Contents")] = writer._add_object(stream)
    if encrypted:
        writer.encrypt("synthetic-password")
    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()


def docx() -> bytes:
    document = WordDocument()
    document.add_paragraph("Párrafo sintético")
    table = document.add_table(rows=1, cols=2)
    table.cell(0, 0).text = "Celda A"
    table.cell(0, 1).text = "Celda B"
    output = io.BytesIO()
    document.save(output)
    return output.getvalue()


def setup(tmp_path, **limits):
    settings = ResearchDevSettings(
        research_db_path=tmp_path / "research.sqlite3",
        research_documents_path=tmp_path / "documents",
        **limits,
    )
    client = TestClient(create_app(settings=settings))
    project_id = client.post("/api/research/projects", json=PROJECT).json()["id"]
    return client, settings, project_id


def upload(client, project_id, name, data):
    response = client.post(
        f"/api/research/projects/{project_id}/documents",
        content=data,
        headers={"X-File-Name": name},
    )
    assert response.status_code == 201
    return response.json()["id"]


def route(project_id, document_id):
    return f"/api/research/projects/{project_id}/documents/{document_id}"


def test_pdf_text_cache_persistence_and_delete(tmp_path):
    client, settings, project = setup(tmp_path)
    document = upload(client, project, "synthetic.pdf", pdf("Synthetic text"))
    url = route(project, document)
    assert client.get(url + "/extraction").status_code == 404
    first = client.post(url + "/extract")
    assert first.status_code == 200
    assert first.json()["status"] == "completed"
    assert "Synthetic text" in first.json()["text"]
    assert first.json()["units_processed"] == 1
    assert client.post(url + "/extract").json() == first.json()
    restarted = TestClient(create_app(settings=settings))
    assert restarted.get(url + "/extraction").json() == first.json()
    assert restarted.delete(url).status_code == 204
    assert restarted.get(url + "/extraction").status_code == 404
    with sqlite3.connect(settings.research_db_path) as connection:
        assert connection.execute("SELECT count(*) FROM research_extractions").fetchone()[0] == 0


def test_docx_paragraphs_tables_and_limits(tmp_path):
    client, _, project = setup(tmp_path, research_extraction_max_characters=25)
    document = upload(client, project, "synthetic.docx", docx())
    result = client.post(route(project, document) + "/extract").json()
    assert result["status"] == "completed"
    assert "Párrafo sintético" in result["text"]
    assert "Celda" in result["text"]
    assert result["truncated"] is True
    assert result["character_count"] <= 25


def test_no_text_pdf_and_docx(tmp_path):
    client, _, project = setup(tmp_path)
    empty_docx = WordDocument()
    stream = io.BytesIO()
    empty_docx.save(stream)
    for name, data in (("scan.pdf", pdf()), ("empty.docx", stream.getvalue())):
        document = upload(client, project, name, data)
        result = client.post(route(project, document) + "/extract").json()
        assert result["status"] == "no_text"
        assert result["warnings"]
        if name.endswith("pdf"):
            assert "OCR" in result["warnings"][0]


def test_invalid_and_protected_files(tmp_path):
    client, _, project = setup(tmp_path)
    invalid_docx = io.BytesIO()
    with zipfile.ZipFile(invalid_docx, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr("word/document.xml", "<invalid/>")
    for name, data in (
        ("protected.pdf", pdf("Hidden", encrypted=True)),
        ("broken.pdf", b"%PDF-1.4\ninvalid\n%%EOF"),
        ("broken.docx", invalid_docx.getvalue()),
    ):
        document = upload(client, project, name, data)
        result = client.post(route(project, document) + "/extract").json()
        assert result["status"] == "failed"
        assert not result["text"]
        assert result["warnings"]


def test_project_ownership_and_missing_document(tmp_path):
    client, _, project = setup(tmp_path)
    other = client.post("/api/research/projects", json=PROJECT).json()["id"]
    document = upload(client, project, "synthetic.pdf", pdf("Owned"))
    for target in (route(other, document), route(project, uuid4())):
        assert client.post(target + "/extract").status_code == 404
        assert client.get(target + "/extraction").status_code == 404


def test_page_limit(tmp_path):
    client, _, project = setup(tmp_path, research_extraction_max_pages=1)
    document = upload(client, project, "synthetic.pdf", pdf("Page", pages=2))
    result = client.post(route(project, document) + "/extract").json()
    assert result["units_processed"] == 1
    assert result["truncated"] is True


def test_content_and_unit_limits(tmp_path):
    client, _, project = setup(
        tmp_path,
        research_extraction_max_content_bytes=1,
        research_extraction_max_units=1,
    )
    pdf_id = upload(client, project, "synthetic.pdf", pdf("Too much"))
    pdf_result = client.post(route(project, pdf_id) + "/extract").json()
    assert pdf_result["status"] == "failed"
    docx_id = upload(client, project, "synthetic.docx", docx())
    docx_result = client.post(route(project, docx_id) + "/extract").json()
    assert docx_result["truncated"] is True
    assert docx_result["units_processed"] == 1


def test_project_delete_removes_extraction(tmp_path):
    client, settings, project = setup(tmp_path)
    document = upload(client, project, "synthetic.pdf", pdf("Synthetic"))
    assert client.post(route(project, document) + "/extract").status_code == 200
    assert client.delete(f"/api/research/projects/{project}").status_code == 204
    with sqlite3.connect(settings.research_db_path) as connection:
        assert connection.execute("SELECT count(*) FROM research_extractions").fetchone()[0] == 0
