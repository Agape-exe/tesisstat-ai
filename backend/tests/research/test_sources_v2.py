import hashlib
import io
import json
import sqlite3
import subprocess
import sys
import zipfile
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from openpyxl import Workbook
from openpyxl.chart import BarChart, Reference

from app.modules.research.context.repository import ContextError
from app.modules.research.datasets.hashing import compute_dataset_hash
from app.modules.research.datasets.models import Dataset
from app.modules.research.datasets.readers import DatasetLimits
from app.modules.research.dev_app import ResearchDevSettings, create_app
from app.modules.research.sources.models import SheetPatch, TableContextPatch
from app.modules.research.sources.readers import WorkbookLimits, inventory
from scripts.create_s03a_examples import csv_bytes, workbook_bytes


@pytest.fixture
def setup(tmp_path):
    settings = ResearchDevSettings(
        _env_file=None,
        research_db_path=tmp_path / "projects.sqlite3",
        research_documents_path=tmp_path / "documents",
        research_datasets_path=tmp_path / "datasets",
    )
    app = create_app(settings=settings)
    with TestClient(app) as client:
        project = client.post("/api/research/projects", json={"title": "Estudio sintético"}).json()
        root = f"/api/v2/research/projects/{project['id']}"
        yield client, root, settings, app.state.source_service


def upload(client, root, data=None, name="mediciones.xlsx"):
    return client.post(
        root + "/files",
        content=workbook_bytes() if data is None else data,
        headers={"X-File-Name": name},
    )


def sheet_change(client, root, source, sheet, action, **extra):
    return client.patch(
        f"{root}/files/{source['id']}/sheets/{sheet['id']}",
        json={"expected_revision": sheet["revision"], "action": action, **extra},
    )


def test_all_sheets_defaults_complete_rows_values_and_original(setup):
    client, root, _, service = setup
    original = workbook_bytes()
    assert original == workbook_bytes()
    response = upload(client, root, original)
    assert response.status_code == 201, response.text
    source = response.json()
    assert source["state"] == "needs_clarification"
    assert [s["name"] for s in source["sheets"]] == [
        "Instrucciones",
        "Antes",
        "Después",
        "Instrumento",
        "Vacía",
        "Con título",
    ]
    assert [s["state"] for s in source["sheets"]] == [
        "pending",
        "ready",
        "ready",
        "ready",
        "pending",
        "pending",
    ]
    assert source["sheets"][3]["visibility"] == "hidden"
    assert len({s["id"] for s in source["sheets"]}) == 6
    tables = client.get(root + "/tables").json()
    assert len(tables) == 3 and len({t["id"] for t in tables}) == 3
    before = source["sheets"][1]
    table, rows = service.read_table(source["project_id"], before["table_id"])
    assert len(rows) == table.row_count == 123
    assert rows[0] == ["0001", "2", "A"] and rows[-1][0] == "0123"
    assert rows[6][1] is None
    preview = client.get(f"{root}/tables/{table.id}/preview").json()
    assert preview["rows"] == rows[:20]
    assert preview["table"]["row_count"] == 123
    after = client.get(f"{root}/tables/{source['sheets'][2]['table_id']}/preview").json()
    assert after["rows"][1][1] == "=1+2"
    assert "fórmulas" in " ".join(after["table"]["warnings"])
    saved_original = client.get(f"{root}/files/{source['id']}/original")
    assert saved_original.content == original
    assert hashlib.sha256(saved_original.content).hexdigest() == source["hash"]
    objects = list(service.repository.storage_path.glob("*.original"))
    assert len(objects) == 1 and objects[0].read_bytes() == original
    assert not list(service.repository.storage_path.glob("*.pending.json"))


def test_confirm_range_exclude_reinclude_cas_and_second_file(setup):
    client, root, _, service = setup
    source = upload(client, root).json()
    titled = source["sheets"][-1]
    invalid = sheet_change(client, root, source, titled, "extract", header_row=2, range="A3:B40")
    assert invalid.status_code == 422
    assert client.get(root + "/files").json()[0] == source
    response = sheet_change(client, root, source, titled, "extract", header_row=3, range="A3:B40")
    assert response.status_code == 200, response.text
    source = response.json()
    titled = source["sheets"][-1]
    table, rows = service.read_table(source["project_id"], titled["table_id"])
    assert len(rows) == 37 and rows[-1] == ["T037", "37"]
    assert table.extraction.header_row == 3 and table.extraction.range == "A3:B40"
    assert table.extraction.confirmation.actor_ref == "local"
    assert table.extraction.confirmation.revision == 2
    old = titled.copy()
    source = sheet_change(client, root, source, titled, "exclude").json()
    excluded = source["sheets"][-1]
    assert excluded["state"] == "excluded"
    assert sheet_change(client, root, source, old, "include").status_code == 409
    assert len(client.get(root + "/tables").json()) == 3
    source = sheet_change(client, root, source, excluded, "include").json()
    assert source["sheets"][-1]["table_id"] == table.id
    assert service.read_table(source["project_id"], table.id)[1] == rows
    for index in (0, 4):
        source = sheet_change(client, root, source, source["sheets"][index], "exclude").json()
    assert source["state"] == "complete"
    independent = upload(client, root, csv_bytes(), "independiente.csv").json()
    assert independent["state"] == "complete"
    assert len(client.get(root + "/files").json()) == 2
    assert len(client.get(root + "/tables").json()) == 5
    with service.repository.connect() as db:
        revisions = db.execute(
            "SELECT COUNT(*) FROM source_file_revisions_v2 WHERE file_id=?", (source["id"],)
        ).fetchone()[0]
    assert revisions == source["revision"]


def test_context_optional_confirm_preserve_null_history_and_conflict(setup):
    client, root, _, _ = setup
    source = upload(client, root).json()
    first, second = [s["table_id"] for s in source["sheets"][1:3]]
    url = f"{root}/tables/{first}/context"
    table = client.get(f"{root}/tables/{first}").json()
    original_hash = table["content_hash"]
    virtual = client.get(url).json()
    assert virtual["revision"] == 0 and virtual["measurement_moment"]["value"] == "unknown"
    assert client.get(url + "/revisions").json() == []
    changes = {
        "name": "  Notas iniciales  ",
        "row_meaning": "Un alumno",
        "identifier_column_id": table["columns"][0]["id"],
    }
    one = client.patch(url, json={"expected_revision": 0, "changes": changes}).json()
    assert one["name"]["value"] == "Notas iniciales"
    assert one["name"]["provenance"]["kind"] == "manual"
    assert one["name"]["confirmation"] is None
    two = client.patch(
        url, json={"expected_revision": 1, "confirm_fields": ["/name", "/identifier_column_id"]}
    ).json()
    assert two["name"]["confirmation"]["revision"] == 2
    assert two["name"]["confirmation"]["actor_ref"] == "local"
    three = client.patch(
        url, json={"expected_revision": 2, "changes": {"purpose": "Comparar más adelante"}}
    ).json()
    assert three["name"] == two["name"] and three["row_meaning"] == two["row_meaning"]
    assert (
        client.patch(
            url, json={"expected_revision": 2, "changes": {"name": "Borrador"}}
        ).status_code
        == 409
    )
    four = client.patch(url, json={"expected_revision": 3, "changes": {"name": None}}).json()
    assert four["name"]["value"] is None and four["name"]["confirmation"] is None
    assert [c["revision"] for c in client.get(url + "/revisions").json()] == [4, 3, 2, 1]
    assert client.get(f"{root}/tables/{second}/context").json()["revision"] == 0
    assert client.get(f"{root}/tables/{first}").json()["content_hash"] == original_hash
    for body in (
        {"expected_revision": 4, "changes": {"identifier_column_id": "foreign-column"}},
        {"expected_revision": 4, "confirm_fields": ["/measurement_moment"]},
        {"expected_revision": 4, "confirm_fields": ["/no-field"]},
        {"expected_revision": 4, "actor_ref": "fake", "changes": {"name": "X"}},
        {"expected_revision": True, "changes": {"name": "X"}},
        {"expected_revision": 4, "changes": {"description": {"value": "fake"}}},
    ):
        assert client.patch(url, json=body).status_code == 422
    assert client.get(url).json() == four


def test_project_and_parent_isolation(setup):
    client, root, _, _ = setup
    source = upload(client, root).json()
    other_file = upload(client, root, csv_bytes(), "otro.csv").json()
    sheet = source["sheets"][1]
    table_id = sheet["table_id"]
    other = client.post("/api/research/projects", json={"title": "Otro"}).json()
    for project in (other["id"], str(uuid4()), "invalid"):
        foreign = f"/api/v2/research/projects/{project}"
        for suffix in (
            f"/tables/{table_id}",
            f"/tables/{table_id}/preview",
            f"/tables/{table_id}/context",
            f"/tables/{table_id}/context/revisions",
            f"/files/{source['id']}/original",
        ):
            assert client.get(foreign + suffix).status_code == 404
        assert (
            client.patch(
                f"{foreign}/tables/{table_id}/context",
                json={"expected_revision": 0, "changes": {"name": "No"}},
            ).status_code
            == 404
        )
    assert client.get(f"/api/v2/research/projects/{other['id']}/files").json() == []
    assert sheet_change(client, root, other_file, sheet, "exclude").status_code == 404
    assert client.get(root + "/files").json()[1] == source


def test_restart_and_separate_process_keep_sources_selection_context_and_bytes(setup):
    client, root, settings, service = setup
    source = upload(client, root).json()
    source = sheet_change(client, root, source, source["sheets"][0], "exclude").json()
    table_id = source["sheets"][1]["table_id"]
    url = f"{root}/tables/{table_id}/context"
    context = client.patch(
        url,
        json={
            "expected_revision": 0,
            "changes": {"measurement_moment": "before"},
            "confirm_fields": ["/measurement_moment"],
        },
    ).json()
    with TestClient(create_app(settings=settings)) as restarted:
        assert restarted.get(root + "/files").json() == [source]
        assert restarted.get(url).json() == context
        assert restarted.get(f"{root}/files/{source['id']}/original").content == workbook_bytes()
    program = (
        "from pathlib import Path; import sys; "
        "from app.modules.research.sources.repository import SourceRepository; "
        "r=SourceRepository(Path(sys.argv[1]),Path(sys.argv[2])); "
        "print(r.context(sys.argv[3],sys.argv[4]).model_dump_json())"
    )
    result = subprocess.run(
        [
            sys.executable,
            "-X",
            "utf8",
            "-c",
            program,
            str(settings.research_db_path),
            str(service.repository.storage_path),
            source["project_id"],
            table_id,
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    assert json.loads(result.stdout) == context


def test_atomic_concurrent_context_and_sheet_revisions(setup):
    client, root, _, service = setup
    source = upload(client, root).json()
    sheet = source["sheets"][1]

    def edit(name):
        try:
            return service.patch_context(
                source["project_id"],
                sheet["table_id"],
                TableContextPatch(expected_revision=0, changes={"name": name}),
            ).revision
        except ContextError as exc:
            return exc.status

    with ThreadPoolExecutor(2) as pool:
        assert sorted(pool.map(edit, ["Primero", "Segundo"])) == [1, 409]

    def exclude(_):
        try:
            return service.change_sheet(
                source["project_id"],
                source["id"],
                sheet["id"],
                SheetPatch(expected_revision=1, action="exclude"),
            ).revision
        except ContextError as exc:
            return exc.status

    with ThreadPoolExecutor(2) as pool:
        assert sorted(pool.map(exclude, range(2))) == [2, 409]


def test_publication_rolls_back_on_disk_and_sqlite_failure_and_recovers_manifest(
    setup, monkeypatch
):
    client, root, settings, service = setup
    original_insert = service.repository._insert_tables

    def fail(*_):
        raise sqlite3.OperationalError("synthetic storage failure")

    monkeypatch.setattr(service.repository, "_insert_tables", fail)
    assert upload(client, root).status_code == 503
    assert client.get(root + "/files").json() == []
    assert not list(service.repository.storage_path.glob("*.original"))
    assert not list(service.repository.storage_path.glob("*.table"))
    monkeypatch.setattr(service.repository, "_insert_tables", original_insert)
    write = Path.open

    def disk_full(path, mode="r", *args, **kwargs):
        if path.suffix == ".table" and mode == "xb":
            raise OSError("synthetic disk full")
        return write(path, mode, *args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(Path, "open", disk_full)
        assert upload(client, root).status_code == 503
    assert client.get(root + "/files").json() == []
    source = upload(client, root).json()
    key = str(uuid4())
    orphan = service.repository.path("table", key)
    orphan.write_bytes(b"synthetic orphan")
    manifest = service.repository.storage_path / "synthetic.pending.json"
    manifest.write_text(
        json.dumps(
            [
                {
                    "kind": "table",
                    "id": key,
                    "hash": hashlib.sha256(orphan.read_bytes()).hexdigest(),
                },
                {"kind": "original", "id": source["id"], "hash": source["hash"]},
            ]
        )
    )
    assert len(service.repository.recover()) == 2 and orphan.exists()
    service.repository.recover(apply=True)
    assert not orphan.exists() and not manifest.exists()
    assert client.get(f"{root}/files/{source['id']}/original").content == workbook_bytes()
    service.repository.path("original", source["id"]).write_bytes(b"corrupted")
    assert client.get(f"{root}/files/{source['id']}/original").status_code == 503


@pytest.mark.parametrize(
    "field,value",
    [("max_sheets", 3), ("max_rows", 20), ("max_cells", 20), ("max_materialized_bytes", 30)],
)
def test_global_limits_reject_entire_publication(setup, field, value):
    client, root, _, service = setup
    service.workbook_limits = replace(WorkbookLimits(), **{field: value})
    response = upload(client, root)
    assert response.status_code == 413, response.text
    assert client.get(root + "/files").json() == []


@pytest.mark.parametrize(
    "data,name,status",
    [
        (b"", "x.xlsx", 422),
        (b"invalid", "x.xlsx", 422),
        (b"a,b\n1\n", "x.csv", 422),
        (b"a,b\n1,2", "x.xlsm", 415),
        (b"x", "../x.csv", 422),
        (b"a,b\n1,2\n", "x.csv", 201),
    ],
)
def test_invalid_formats_and_csv(setup, data, name, status):
    client, root, _, _ = setup
    assert upload(client, root, data, name).status_code == status


def test_macros_zip_and_table_limits_and_missing_dimension_rows():
    data = workbook_bytes()
    with zipfile.ZipFile(io.BytesIO(data)) as original:
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as target:
            for name in original.namelist():
                content = original.read(name)
                if name == "xl/worksheets/sheet2.xml":
                    content = content.replace(b'ref="A1:C124"', b'ref="A1:C2"')
                target.writestr(name, content)
        raw = inventory(buffer.getvalue(), "xlsx", DatasetLimits(), WorkbookLimits())
        assert len(raw[1].rows) == 124
        with zipfile.ZipFile(buffer, "a") as target:
            target.writestr("xl/vbaProject.bin", b"synthetic")
        with pytest.raises(ContextError, match="macros"):
            inventory(buffer.getvalue(), "xlsx", DatasetLimits(), WorkbookLimits())
    for limits in (
        DatasetLimits(max_zip_bytes=2),
        DatasetLimits(max_zip_entries=1),
        DatasetLimits(max_rows=5),
        DatasetLimits(max_columns=2),
        DatasetLimits(max_bytes=2),
    ):
        with pytest.raises(ContextError) as error:
            inventory(data, "xlsx", limits, WorkbookLimits())
        assert error.value.status == 413


def test_same_headers_are_different_sources_and_legacy_active_hash_unchanged(setup):
    client, root, _, _ = setup
    project_id = root.rsplit("/", 1)[-1]
    legacy_root = f"/api/research/projects/{project_id}/datasets"
    legacy = client.post(
        legacy_root, content=csv_bytes(), headers={"X-File-Name": "legado.csv"}
    ).json()
    client.post(f"{legacy_root}/{legacy['id']}/activate")
    before = client.get(legacy_root).json()
    legacy_hash = compute_dataset_hash(Dataset.model_validate(legacy), csv_bytes())
    source = upload(client, root).json()
    first, second = source["sheets"][1:3]
    assert first["table_id"] != second["table_id"]
    client.get(f"{root}/tables/{second['table_id']}/preview")
    assert client.get(legacy_root).json() == before
    # v1 source and its hash algorithm are never modified by v2 context/ingestion.
    assert (
        compute_dataset_hash(
            Dataset.model_validate(client.get(f"{legacy_root}/{legacy['id']}").json()), csv_bytes()
        )
        == legacy_hash
    )
    assert client.get(f"{legacy_root}/{legacy['id']}/preview").json()["row_count"] == 27


def test_single_column_and_title_and_duplicate_headers_need_clarification(setup):
    client, root, _, _ = setup
    book = Workbook()
    first = book.active
    first.append(["Instrucción"])
    first.append(["No son observaciones"])
    duplicate = book.create_sheet("Duplicados")
    duplicate.append(["id", "id"])
    duplicate.append(["001", "002"])
    normal = book.create_sheet("Normal")
    normal.append(["id", "valor"])
    normal.append(["001", "2"])
    buffer = io.BytesIO()
    book.save(buffer)
    source = upload(client, root, buffer.getvalue()).json()
    assert [s["state"] for s in source["sheets"]] == ["pending", "pending", "ready"]
    assert len(client.get(root + "/tables").json()) == 1


def test_exact_text_values_and_server_resolved_refs_and_excluded_read(setup):
    client, root, _, service = setup
    source = upload(
        client, root, b"id,value\n 001 , text with spaces \n0002,=1+2\n", "texto.csv"
    ).json()
    table_id = source["sheets"][0]["table_id"]
    preview = client.get(f"{root}/tables/{table_id}/preview").json()
    assert preview["rows"] == [[" 001 ", " text with spaces "], ["0002", "=1+2"]]
    refs = service.source_refs(source["project_id"], table_id)
    assert [r.kind for r in refs] == ["source_file", "source_sheet", "table"]
    assert refs[0].hash == source["hash"]
    client.patch(
        f"{root}/tables/{table_id}/context",
        json={"expected_revision": 0, "changes": {"name": "Texto exacto"}},
    )
    refs = service.source_refs(source["project_id"], table_id)
    assert refs[-1].kind == "table_context" and refs[-1].revision == 1
    source = sheet_change(client, root, source, source["sheets"][0], "exclude").json()
    assert client.get(f"{root}/tables/{table_id}/preview").status_code == 409
    assert client.get(f"{root}/tables/{table_id}/context").status_code == 200


def test_charts_and_merged_cells_remain_pending_without_blocking_normal_sheet(setup):
    client, root, _, _ = setup
    book = Workbook()
    normal = book.active
    normal.title = "Tabla"
    normal.append(["codigo", "nota"])
    normal.append(["0001", 12])
    normal.append(["0002", 14])
    chart = BarChart()
    chart.add_data(Reference(normal, min_col=2, min_row=1, max_row=3), titles_from_data=True)
    chart_sheet = book.create_chartsheet("Gráfico")
    chart_sheet.add_chart(chart)
    merged = book.create_sheet("Combinadas")
    merged.append(["codigo", "nota"])
    merged.append(["0001", "Texto combinado"])
    merged.append(["0002", None])
    merged.merge_cells("B2:B3")
    buffer = io.BytesIO()
    book.save(buffer)
    source = upload(client, root, buffer.getvalue()).json()
    assert [s["name"] for s in source["sheets"]] == ["Tabla", "Gráfico", "Combinadas"]
    assert [s["state"] for s in source["sheets"]] == ["ready", "pending", "pending"]
    source = sheet_change(
        client, root, source, source["sheets"][2], "extract", header_row=1, range="A1:B3"
    ).json()
    table_id = source["sheets"][2]["table_id"]
    preview = client.get(f"{root}/tables/{table_id}/preview").json()
    assert preview["rows"][1][1] is None
    assert "combinadas" in " ".join(preview["table"]["warnings"])


def test_failed_pending_extraction_preserves_existing_publication(setup, monkeypatch):
    client, root, _, service = setup
    source = upload(client, root).json()
    tables_before = client.get(root + "/tables").json()

    def fail(*_):
        raise sqlite3.OperationalError("synthetic publication failure")

    monkeypatch.setattr(service.repository, "_insert_tables", fail)
    response = sheet_change(
        client, root, source, source["sheets"][-1], "extract", header_row=3, range="A3:B40"
    )
    assert response.status_code == 503
    assert client.get(root + "/files").json() == [source]
    assert client.get(root + "/tables").json() == tables_before
    assert len(list(service.repository.storage_path.glob("*.table"))) == 3
    assert client.get(f"{root}/files/{source['id']}/original").content == workbook_bytes()


@pytest.mark.parametrize("target", ["xl/workbook.xml", "xl/styles.xml", "xl/worksheets/sheet2.xml"])
def test_malformed_workbook_xml_returns_clear_422_without_publication(setup, target):
    client, root, _, _ = setup
    output = io.BytesIO()
    with (
        zipfile.ZipFile(io.BytesIO(workbook_bytes())) as source,
        zipfile.ZipFile(output, "w") as dest,
    ):
        for name in source.namelist():
            dest.writestr(name, b"<invalid" if name == target else source.read(name))
    response = upload(client, root, output.getvalue())
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_payload"
    assert client.get(root + "/files").json() == []
