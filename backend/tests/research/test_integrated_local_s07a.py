"""Integrated local acceptance evidence; no remote identity or provider simulated as real."""

import hashlib
import json
import shutil
import sqlite3
from io import BytesIO

import pytest
from docx import Document
from fastapi.testclient import TestClient
from pypdf import PdfReader
from scipy import stats

from app.modules.research.dev_app import create_app
from tests.research.test_analysis_workflow_v2 import (
    test_real_selector_and_execution as run_analysis,
)
from tests.research.test_diagnostics_v2 import setup as setup
from tests.research.test_instruments_v2 import env as env
from tests.research.test_score_chains_v2 import b_analysis, chain
from tests.research.test_tutor_v2 import send, tutor


@pytest.mark.parametrize(
    "kind,estimand,observations,technique,key",
    [
        ("association", "linear_association", "independent", "pearson", "r"),
        ("association", "monotonic_association", "independent", "spearman", "rho"),
        ("comparison", "mean_difference", "independent", "t_welch", "t_statistic"),
        ("comparison", "distribution_difference", "independent", "mann_whitney", "u"),
        ("comparison", "mean_difference", "paired", "t_paired", "t_statistic"),
        ("comparison", "distribution_difference", "paired", "wilcoxon", "w"),
    ],
)
def test_integrated_numbers_figures_and_three_reports(
    setup, kind, estimand, observations, technique, key
):
    run_analysis(setup, kind, estimand, observations, technique)
    c, root, _, _ = setup
    result = c.get(root + "/analysis/results").json()[0]
    x, y = [1, 2, 4, 8, 5, 7], [3, 6, 5, 9, 10, 13]
    references = {
        "pearson": lambda: stats.pearsonr(x, y),
        "spearman": lambda: stats.spearmanr(x, y),
        "t_welch": lambda: stats.ttest_ind(x[:3], x[3:], equal_var=False),
        "mann_whitney": lambda: stats.mannwhitneyu(x[:3], x[3:], method="exact"),
        "t_paired": lambda: stats.ttest_rel(x, y),
        "wilcoxon": lambda: stats.wilcoxon(x, y, method="approx", correction=True),
    }
    reference = references[technique]()
    metrics = {m["key"]: m["value"] for m in result["metrics"]}
    assert metrics[key] == pytest.approx(reference.statistic, rel=1e-6, abs=1e-8)
    assert metrics["p_value"] == pytest.approx(reference.pvalue, rel=1e-5, abs=1e-8)
    assert result["case_counts"]["total"] == 7
    assert result["case_counts"]["excluded"] == 1
    if observations == "paired":
        assert result["case_counts"]["pairs"] == 6
    url = root + f"/analysis/results/{result['id']}"
    assert c.get(url + "/figures").status_code == 200
    presentation = c.get(url + "/presentation").json()
    expected = next(m["formatted"] for m in presentation["metrics"] if m["key"] == key)
    for fmt in ("txt", "docx", "pdf"):
        response = c.get(url + f"/export?format={fmt}")
        assert response.status_code == 200, response.text
        assert response.headers["cache-control"] == "no-store"
        if fmt == "txt":
            text = response.content.decode()
        elif fmt == "docx":
            doc = Document(BytesIO(response.content))
            text = "\n".join(p.text for p in doc.paragraphs)
            text += "\n".join(
                cell.text for table in doc.tables for row in table.rows for cell in row.cells
            )
        else:
            text = "\n".join(p.extract_text() for p in PdfReader(BytesIO(response.content)).pages)
        assert expected in text
        assert "NaN" not in text and "Infinity" not in text
    assert c.get(url).json() == result


def database_manifest(path):
    """Logical hashes include blobs; independent of SQLite physical page layout."""
    with sqlite3.connect(path) as db:
        assert db.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        names = [
            r[0]
            for r in db.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        ]
        result = {}
        for name in names:
            escaped = name.replace('"', '""')
            rows = db.execute(f'SELECT * FROM "{escaped}"').fetchall()
            encoded = sorted(
                json.dumps(row, ensure_ascii=False, default=lambda b: {"hex": b.hex()})
                for row in rows
            )
            result[name] = {
                "count": len(rows),
                "sha256": hashlib.sha256("\n".join(encoded).encode()).hexdigest(),
            }
        return result


def object_manifest(directory):
    return {
        str(p.relative_to(directory)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in directory.rglob("*")
        if p.is_file() and not p.name.startswith(("db.sqlite3", "projects.sqlite3"))
    }


def test_restore_complete_local_tree_in_another_directory(env, tmp_path):
    c, root, app, settings = env
    values = chain(env, prepared_source=True)
    result = b_analysis(env, values)
    _, _, provider, cid = tutor(
        env,
        {
            "response_version": "tutor-2.1",
            "concepts": ["La media resume valores cuantitativos."],
            "findings": [{"kind": "case_counts"}],
        },
    )
    answer = send(c, root, cid, stage="results", result_id=result["id"])
    assert answer.status_code == 200, answer.text
    assert len(provider.calls) == 1
    suggestion = c.post(
        root + "/context/suggestions",
        json={
            "expected_revision": 1,
            "response": json.dumps(
                {
                    "format_version": "context-import-1.0",
                    "main_objective": "Describir experiencia sintética",
                }
            ),
        },
    )
    assert suggestion.status_code == 201, suggestion.text
    paths = [
        "/context",
        "/context/revisions",
        "/context/suggestions",
        "/files",
        "/data-tables",
        "/intents",
        "/analysis/plans",
        "/analysis/results",
        "/conversations/consent",
        f"/analysis/results/{result['id']}/interpretations",
    ]
    for owner in ("A", "B"):
        instrument = values[owner]["instrument_id"]
        paths += [
            f"/instruments/{instrument}",
            f"/instruments/{instrument}/mapping",
            f"/instruments/{instrument}/scores",
        ]
        table = values[f"{owner}_score"]["derived_dataset_ref"]["id"]
        paths += [f"/data-tables/{table}/preview", f"/data-tables/{table}/dictionary"]
    expected = {path: c.get(root + path).json() for path in paths}
    old = root.replace("/api/v2/", "/api/") + f"/conversations/{cid}"
    conversation = c.get(old).json()
    original = c.get(root + "/files").json()[0]
    original_bytes = c.get(root + f"/files/{original['id']}/original").content
    before = database_manifest(settings.research_db_path)
    # Fixture is quiescent: no server, upload or worker runs during this copy.
    backup = tmp_path / "backup"
    restored = tmp_path / "restored"
    backup.mkdir()
    with (
        sqlite3.connect(settings.research_db_path) as source_db,
        sqlite3.connect(backup / "db.sqlite3") as dest,
    ):
        source_db.backup(dest)
    for directory in list(tmp_path.iterdir()):
        if directory.is_dir() and directory != backup:
            shutil.copytree(directory, backup / directory.name)
    shutil.copytree(backup, restored)
    assert database_manifest(restored / "db.sqlite3") == before
    assert object_manifest(restored) == object_manifest(backup)
    new_settings = settings.model_copy(
        update={
            "research_db_path": restored / "db.sqlite3",
            "research_documents_path": restored / "documents",
            "research_datasets_path": restored / "datasets",
        }
    )
    with TestClient(create_app(settings=new_settings)) as recovered:
        for path, payload in expected.items():
            response = recovered.get(root + path)
            assert response.status_code == 200, (path, response.text)
            assert response.json() == payload, path
        assert recovered.get(old).json() == conversation
        assert recovered.get(root + f"/files/{original['id']}/original").content == original_bytes
        assert (
            recovered.get(root + f"/analysis/results/{result['id']}/export?format=pdf").status_code
            == 200
        )
    assert database_manifest(settings.research_db_path) == before
