from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from uuid import uuid4
from zipfile import ZipFile

import pytest
from docx import Document
from fastapi.testclient import TestClient
from pypdf import PdfReader

from app.modules.research.dev_app import create_app
from tests.research.test_analysis_workflow_v2 import approve, execute, proposal
from tests.research.test_diagnostics_v2 import diagnose
from tests.research.test_diagnostics_v2 import setup as setup


def prepare(client, root):
    upload = client.post(
        root + "/files",
        content=(b"codigo,promedio,ganancia,grupo\na,10,2,A\nb,14,4,B\nc,18,6,A\nd,,8,B\n"),
        headers={"X-File-Name": "sintetico.csv"},
    )
    assert upload.status_code == 201, upload.text
    table = upload.json()["sheets"][0]["table_id"]
    selection = {"stage": "data", "dataset_id": table}
    response = client.get(root + "/conversations/status", params=selection)
    assert response.status_code == 200, response.text
    status = response.json()
    body = {
        "kind": "prepare_descriptive",
        "selection": selection,
        "context_fingerprint": status["context"]["context_fingerprint"],
        "request_id": str(uuid4()),
        "confirm": True,
        "variables": [
            {"variable_id": v["variable_id"], "measurement_scale": "interval"}
            for v in status["guidance"]["variables"]
            if v["selected"]
        ],
    }
    return table, status, body


def test_guided_descriptive_no_context_selected_only_complete_flow_and_real_graphics(setup):
    client, root, app, settings = setup
    table, status, body = prepare(client, root)
    assert status["guidance"]["selected_table"]["rows"] == 4
    assert len(body["variables"]) == 2
    assert status["consent"]["granted"] is False
    response = client.post(root + "/conversations/actions", json=body)
    assert response.status_code == 200, response.text
    intent_id = response.json()["intent_id"]
    assert client.post(root + "/conversations/actions", json=body).json()["intent_id"] == intent_id
    dictionary = client.get(root + f"/data-tables/{table}/dictionary").json()
    assert sum(bool(v["measurement_scale"]["confirmation"]) for v in dictionary["variables"]) == 2
    assert client.get(root + "/context").json()["revision"] == 0
    intent = client.get(root + f"/intents/{intent_id}").json()
    assert intent["observations"]["value"] == "unknown"
    diagnostic = diagnose(client, root, intent, ["complete_cases", "distribution"])
    assert diagnostic.status_code == 201, diagnostic.text
    plan = proposal(client, root, intent, [diagnostic.json()["id"]])
    assert plan["technique"] == "descriptive_summary"
    assert execute(client, root, plan).status_code == 409
    approve(client, root, plan)
    result = execute(client, root, plan).json()
    assert result["case_counts"]["used"] == 3
    means = [m["value"] for m in result["metrics"] if m["key"].endswith(".mean")]
    assert means == [14, 4]
    endpoint = root + f"/analysis/results/{result['id']}"
    presentation = client.get(endpoint + "/presentation").json()
    assert "media 14" in presentation["interpretation"]
    assert "media 4" in presentation["interpretation"]
    assert "intervalos disponibles" not in presentation["interpretation"]
    figures = client.get(endpoint + "/figures").json()["figures"]
    assert figures[0]["y"] == [14, 14, 4, 4]
    assert figures[0]["axis_min"] == 0 and figures[0]["axis_max"] == 14
    from app.modules.statistics.report_charts_v2 import chart_geometry
    from app.shared.reports_v2 import ResultFigureDataV2

    _, geometry = chart_geometry(ResultFigureDataV2.model_validate(figures[0]))
    bars = [args for kind, args, _ in geometry if kind == "rect"]
    assert (bars[0][2] - bars[0][0]) / (bars[2][2] - bars[2][0]) == pytest.approx(3.5, rel=1e-12)
    doc = client.get(endpoint + "/export?format=docx")
    pdf = client.get(endpoint + "/export?format=pdf")
    assert doc.status_code == pdf.status_code == 200
    with ZipFile(BytesIO(doc.content)) as archive:
        assert any(n.startswith("word/media/") for n in archive.namelist())
        assert "#####" not in archive.read("word/document.xml").decode()
    assert len(Document(BytesIO(doc.content)).inline_shapes) == 1
    reader = PdfReader(BytesIO(pdf.content))
    text = "\n".join(p.extract_text() for p in reader.pages)
    assert "#####" not in text
    assert "Media" in text and "Anexo técnico" in text
    assert "/XObject" in str(reader.pages) or any(
        b" re" in p.get_contents().get_data() for p in reader.pages
    )
    with TestClient(create_app(settings=settings)) as restarted:
        assert (
            restarted.post(root + "/conversations/actions", json=body).json()["intent_id"]
            == intent_id
        )
        assert len(restarted.get(root + "/intents").json()) == 1
        assert restarted.get(endpoint).json()["metrics"] == result["metrics"]


def test_guided_retries_concurrent_and_fingerprint_mismatch(setup):
    client, root, _, _ = setup
    _, _, body = prepare(client, root)
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(
            pool.map(lambda _: client.post(root + "/conversations/actions", json=body), range(2))
        )
    assert all(r.status_code == 200 for r in responses), [r.text for r in responses]
    assert responses[0].json()["intent_id"] == responses[1].json()["intent_id"]
    changed = {**body, "variables": body["variables"][:1]}
    assert client.post(root + "/conversations/actions", json=changed).status_code == 409
    stale = {**body, "request_id": str(uuid4())}
    assert client.post(root + "/conversations/actions", json=stale).status_code == 409


def test_guided_closed_actions_cross_project_and_unreviewed_selection(setup):
    client, root, _, _ = setup
    _, _, body = prepare(client, root)
    for changes in ({"kind": "execute"}, {"confirm": False}, {"code": "print(1)"}):
        assert (
            client.post(root + "/conversations/actions", json={**body, **changes}).status_code
            == 422
        )
    other = client.post("/api/research/projects", json={"title": "Otro proyecto C02"}).json()["id"]
    assert (
        client.post(
            f"/api/v2/research/projects/{other}/conversations/actions", json=body
        ).status_code
        == 404
    )
    invalid = {**body, "variables": [{"variable_id": "ajena", "measurement_scale": "ratio"}]}
    assert client.post(root + "/conversations/actions", json=invalid).status_code == 422
    assert client.get(root + "/intents").json() == []


def test_guided_numeric_codes_can_be_corrected_to_categories(setup):
    client, root, _, _ = setup
    table, _, body = prepare(client, root)
    body["variables"] = [{**body["variables"][0], "measurement_scale": "nominal"}]
    response = client.post(root + "/conversations/actions", json=body)
    assert response.status_code == 200, response.text
    intent = client.get(root + f"/intents/{response.json()['intent_id']}").json()
    plan = proposal(client, root, intent)
    approve(client, root, plan)
    result = execute(client, root, plan).json()
    assert result["metrics"] == []
    assert len(result["tables"][0]["rows"]) == 3
    assert client.get(root + f"/data-tables/{table}/profile").json()["state"] == "current"


def test_guided_failure_rolls_back_dictionary_profile_and_intent(setup, monkeypatch):
    client, root, app, _ = setup
    table, _, body = prepare(client, root)
    original = app.state.analysis_v2.intents.save

    def fail(*args, **kwargs):
        raise RuntimeError("controlled local failure")

    monkeypatch.setattr(app.state.analysis_v2.intents, "save", fail)
    with pytest.raises(RuntimeError, match="controlled local failure"):
        client.post(root + "/conversations/actions", json=body)
    assert client.get(root + f"/data-tables/{table}/dictionary").json()["revision"] == 0
    assert client.get(root + f"/data-tables/{table}/profile").status_code == 404
    monkeypatch.setattr(app.state.analysis_v2.intents, "save", original)
    assert client.post(root + "/conversations/actions", json=body).status_code == 200
    assert len(client.get(root + "/intents").json()) == 1


def test_guided_auto_binds_first_table_when_dataset_id_is_none(setup):
    client, root, _, _ = setup
    upload = client.post(
        root + "/files",
        content=(b"codigo,nota1,nota2\na,15,18\nb,12,14\n"),
        headers={"X-File-Name": "notas.csv"},
    )
    assert upload.status_code == 201
    table_id = upload.json()["sheets"][0]["table_id"]

    # Query status WITHOUT passing dataset_id
    response = client.get(root + "/conversations/status", params={"stage": "data"})
    assert response.status_code == 200
    status = response.json()
    assert status["guidance"]["selected_table"] is not None
    assert status["guidance"]["selected_table"]["id"] == table_id
    assert len(status["guidance"]["variables"]) == 3
    assert any(a["kind"] == "prepare_descriptive" for a in status["context"]["allowed_actions"])
