"""Integration tests for Research Instrument HTTP API endpoints."""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.modules.research.dev_app import ResearchDevSettings, create_app
from app.modules.research.instrument.fixtures import standard_likert_options
from app.modules.research.instrument.models import (
    InstrumentDimension,
    InstrumentIndicator,
    InstrumentItem,
    InstrumentVariable,
    ScoringRule,
)
from app.modules.research.instrument.repository import InstrumentStaleError


def _setup_api(tmp_path):
    settings = ResearchDevSettings(
        research_db_path=tmp_path / "research.sqlite3",
        research_documents_path=tmp_path / "docs",
        research_datasets_path=tmp_path / "datasets",
    )
    app = create_app(settings=settings)
    client = TestClient(app)
    return client, settings, app


def _create_project(client) -> str:
    resp = client.post(
        "/api/research/projects",
        json={
            "title": "Proyecto de Instrumentos Psicométricos",
            "university": "Universidad Nacional",
            "faculty": "Psicología",
            "program": "Organizacional",
            "degree": "bachelor",
        },
    )
    assert resp.status_code == 201
    return resp.json()["id"]


def _upload_document_and_review(client, project_id: str, var_id: UUID) -> str:
    # 1. Subir documento
    doc_resp = client.post(
        f"/api/research/projects/{project_id}/documents",
        content=b"%PDF-1.4\nCuestionario Clima\n%%EOF",
        headers={"X-File-Name": "cuestionario.pdf", "Content-Type": "application/pdf"},
    )
    assert doc_resp.status_code == 201
    doc_id = doc_resp.json()["id"]

    # 2. Crear y confirmar revisión metodológica
    rev_url = f"/api/research/projects/{project_id}/documents/{doc_id}/methodology/review"
    init_rev = client.post(rev_url)
    assert init_rev.status_code == 201

    def _manual(val):
        return {"value": val, "kind": "manual", "evidence": []}

    content = init_rev.json()["content"]
    content["title"] = _manual("Clima Organizacional")
    content["general_objective"] = _manual("Medir el clima")
    content["research_design"] = _manual("Transversal")
    content["specific_objectives"] = [_manual("Evaluar dimensiones")]
    content["specific_hypotheses"] = [_manual("Hipótesis general")]
    content["variables"] = [
        {
            "id": str(var_id),
            "name": _manual("Clima"),
            "role": _manual("independent"),
            "measurement_scale": _manual("ordinal"),
            "dimensions": [_manual("Liderazgo")],
            "indicators": [_manual("Comunicación")],
            "instrument_items": [_manual("Ítem 1")],
        }
    ]
    save_resp = client.put(rev_url, json={"version": 0, "content": content})
    assert save_resp.status_code == 200

    conf_resp = client.post(rev_url + "/confirm", json={"version": 1})
    assert conf_resp.status_code == 200
    assert conf_resp.json()["review_status"] == "reviewed"
    return doc_id


def _upload_dataset(
    client, project_id: str, content: bytes = b"p1,p2,extra\n1,2,x\n3,4,y\n"
) -> str:
    resp = client.post(
        f"/api/research/projects/{project_id}/datasets",
        content=content,
        headers={"X-File-Name": "respuestas.csv", "Content-Type": "text/csv"},
    )
    assert resp.status_code == 201
    return resp.json()["id"]


def _sample_structure():
    var_id = uuid4()
    dim_id = uuid4()
    ind_id = uuid4()
    item1_id = uuid4()
    item2_id = uuid4()
    rule_id = uuid4()

    variable = InstrumentVariable(
        variable_id=var_id,
        name="Clima",
        scale="ordinal",
        methodology_variable_id=var_id,
    )
    dimension = InstrumentDimension(
        dimension_id=dim_id,
        variable_id=var_id,
        name="Liderazgo",
    )
    indicator = InstrumentIndicator(
        indicator_id=ind_id,
        dimension_id=dim_id,
        name="Comunicación",
    )
    opts = standard_likert_options()
    item1 = InstrumentItem(
        item_id=item1_id,
        variable_id=var_id,
        dimension_id=dim_id,
        indicator_id=ind_id,
        text="Mi superior escucha mis propuestas con atención.",
        response_type="single_choice",
        response_options=opts,
        valid_min=1.0,
        valid_max=5.0,
        reverse_scored=False,
    )
    item2 = InstrumentItem(
        item_id=item2_id,
        variable_id=var_id,
        dimension_id=dim_id,
        indicator_id=ind_id,
        text="Rara vez recibo retroalimentación constructiva.",
        response_type="single_choice",
        response_options=opts,
        valid_min=1.0,
        valid_max=5.0,
        reverse_scored=True,
        reverse_rule="min_plus_max_minus_value",
    )
    rule = ScoringRule(
        scoring_rule_id=rule_id,
        scope="dimension",
        dimension_id=dim_id,
        item_ids=[item1_id, item2_id],
        aggregation="sum",
        missing_policy="all_required",
        confirmed=False,
    )
    return [variable], [dimension], [indicator], [item1, item2], [rule]


class TestInstrumentAPIIntegration:
    """End-to-end integration test suite for /api/research/projects/{id}/instruments."""

    def test_1_create_draft(self, tmp_path):
        client, _, _ = _setup_api(tmp_path)
        project_id = _create_project(client)
        vars_, dims, inds, items, rules = _sample_structure()

        body = {
            "variables": [v.model_dump(mode="json") for v in vars_],
            "dimensions": [d.model_dump(mode="json") for d in dims],
            "indicators": [i.model_dump(mode="json") for i in inds],
            "items": [it.model_dump(mode="json") for it in items],
            "scoring_rules": [r.model_dump(mode="json") for r in rules],
        }
        resp = client.post(f"/api/research/projects/{project_id}/instruments", json=body)
        assert resp.status_code == 201
        data = resp.json()
        assert data["version"] == 0
        assert data["status"] == "draft"
        assert data["confirmation"]["state"] == "pending"
        assert resp.headers["Location"].endswith(data["instrument_id"])

    def test_2_get_instrument(self, tmp_path):
        client, _, _ = _setup_api(tmp_path)
        project_id = _create_project(client)
        vars_, dims, inds, items, rules = _sample_structure()
        body = {
            "variables": [v.model_dump(mode="json") for v in vars_],
            "dimensions": [d.model_dump(mode="json") for d in dims],
            "indicators": [i.model_dump(mode="json") for i in inds],
            "items": [it.model_dump(mode="json") for it in items],
            "scoring_rules": [r.model_dump(mode="json") for r in rules],
        }
        create_resp = client.post(f"/api/research/projects/{project_id}/instruments", json=body)
        inst_id = create_resp.json()["instrument_id"]

        get_resp = client.get(f"/api/research/projects/{project_id}/instruments/{inst_id}")
        assert get_resp.status_code == 200
        assert get_resp.json()["instrument_id"] == inst_id

        # Listar instrumentos
        list_resp = client.get(f"/api/research/projects/{project_id}/instruments")
        assert list_resp.status_code == 200
        assert len(list_resp.json()) == 1

    def test_3_update_draft_optimistic(self, tmp_path):
        client, _, _ = _setup_api(tmp_path)
        project_id = _create_project(client)
        vars_, dims, inds, items, rules = _sample_structure()
        body = {
            "variables": [v.model_dump(mode="json") for v in vars_],
            "dimensions": [d.model_dump(mode="json") for d in dims],
            "indicators": [i.model_dump(mode="json") for i in inds],
            "items": [it.model_dump(mode="json") for it in items],
            "scoring_rules": [r.model_dump(mode="json") for r in rules],
        }
        create_resp = client.post(f"/api/research/projects/{project_id}/instruments", json=body)
        inst_id = create_resp.json()["instrument_id"]

        # Modificar texto del ítem
        items[0].text = "Texto actualizado del ítem 1."
        update_body = {
            "expected_version": 0,
            "variables": [v.model_dump(mode="json") for v in vars_],
            "dimensions": [d.model_dump(mode="json") for d in dims],
            "indicators": [i.model_dump(mode="json") for i in inds],
            "items": [it.model_dump(mode="json") for it in items],
            "scoring_rules": [r.model_dump(mode="json") for r in rules],
        }
        put_resp = client.put(
            f"/api/research/projects/{project_id}/instruments/{inst_id}",
            json=update_body,
        )
        assert put_resp.status_code == 200
        updated = put_resp.json()
        assert updated["version"] == 1
        assert updated["items"][0]["text"] == "Texto actualizado del ítem 1."

    def test_4_confirm_instrument(self, tmp_path):
        client, _, _ = _setup_api(tmp_path)
        project_id = _create_project(client)
        vars_, dims, inds, items, rules = _sample_structure()
        doc_id = _upload_document_and_review(client, project_id, vars_[0].variable_id)

        # Regla NO confirmada al inicio
        rules[0].confirmed = False

        create_resp = client.post(
            f"/api/research/projects/{project_id}/instruments",
            json={
                "variables": [v.model_dump(mode="json") for v in vars_],
                "dimensions": [d.model_dump(mode="json") for d in dims],
                "indicators": [i.model_dump(mode="json") for i in inds],
                "items": [it.model_dump(mode="json") for it in items],
                "scoring_rules": [r.model_dump(mode="json") for r in rules],
            },
        )
        inst_id = create_resp.json()["instrument_id"]

        # Vincular metodología
        link_resp = client.post(
            f"/api/research/projects/{project_id}/instruments/{inst_id}/methodology",
            json={"expected_version": 0, "document_id": doc_id},
        )
        assert link_resp.status_code == 200
        assert link_resp.json()["version"] == 1
        assert link_resp.json()["provenance"] is not None

        # Confirmar reglas explícitamente vía endpoint dedicado
        rule_conf_resp = client.post(
            f"/api/research/projects/{project_id}/instruments/{inst_id}/rules/confirm",
            json={"expected_version": 1},
        )
        assert rule_conf_resp.status_code == 200
        assert rule_conf_resp.json()["version"] == 2
        assert rule_conf_resp.json()["scoring_rules"][0]["confirmed"] is True

        # Confirmar instrumento
        conf_resp = client.post(
            f"/api/research/projects/{project_id}/instruments/{inst_id}/confirm",
            json={"expected_version": 2, "confirmer_ref": "metodologo_senior"},
        )
        assert conf_resp.status_code == 200
        confirmed = conf_resp.json()
        assert confirmed["version"] == 3
        assert confirmed["status"] == "reviewed"
        assert confirmed["confirmation"]["state"] == "confirmed"
        assert confirmed["confirmation"]["confirmer_ref"] == "metodologo_senior"

    def test_5_create_mapping(self, tmp_path):
        client, _, _ = _setup_api(tmp_path)
        project_id = _create_project(client)
        vars_, dims, inds, items, rules = _sample_structure()
        dataset_id = _upload_dataset(client, project_id)

        create_resp = client.post(
            f"/api/research/projects/{project_id}/instruments",
            json={
                "variables": [v.model_dump(mode="json") for v in vars_],
                "dimensions": [d.model_dump(mode="json") for d in dims],
                "indicators": [i.model_dump(mode="json") for i in inds],
                "items": [it.model_dump(mode="json") for it in items],
                "scoring_rules": [r.model_dump(mode="json") for r in rules],
            },
        )
        inst_id = create_resp.json()["instrument_id"]

        mapping_body = {
            "expected_version": 0,
            "dataset_id": dataset_id,
            "item_columns": [
                {"item_id": str(items[0].item_id), "column_name": "p1"},
                {"item_id": str(items[1].item_id), "column_name": "p2"},
            ],
        }
        map_resp = client.post(
            f"/api/research/projects/{project_id}/instruments/{inst_id}/mapping",
            json=mapping_body,
        )
        assert map_resp.status_code == 200
        mapped = map_resp.json()
        assert mapped["version"] == 1
        assert mapped["dataset_mapping"]["status"] == "draft"
        assert mapped["dataset_mapping"]["confirmation"]["state"] == "pending"

    def test_6_confirm_mapping(self, tmp_path):
        client, _, _ = _setup_api(tmp_path)
        project_id = _create_project(client)
        vars_, dims, inds, items, rules = _sample_structure()
        dataset_id = _upload_dataset(client, project_id)

        create_resp = client.post(
            f"/api/research/projects/{project_id}/instruments",
            json={
                "variables": [v.model_dump(mode="json") for v in vars_],
                "dimensions": [d.model_dump(mode="json") for d in dims],
                "indicators": [i.model_dump(mode="json") for i in inds],
                "items": [it.model_dump(mode="json") for it in items],
                "scoring_rules": [r.model_dump(mode="json") for r in rules],
            },
        )
        inst_id = create_resp.json()["instrument_id"]

        map_resp = client.post(
            f"/api/research/projects/{project_id}/instruments/{inst_id}/mapping",
            json={
                "expected_version": 0,
                "dataset_id": dataset_id,
                "item_columns": [
                    {"item_id": str(items[0].item_id), "column_name": "p1"},
                    {"item_id": str(items[1].item_id), "column_name": "p2"},
                ],
            },
        )
        assert map_resp.status_code == 200

        conf_resp = client.post(
            f"/api/research/projects/{project_id}/instruments/{inst_id}/mapping/confirm",
            json={"expected_version": 1, "confirmer_ref": "analista_datos"},
        )
        assert conf_resp.status_code == 200
        conf_data = conf_resp.json()
        assert conf_data["version"] == 2
        assert conf_data["dataset_mapping"]["status"] == "confirmed"
        assert conf_data["dataset_mapping"]["confirmation"]["state"] == "confirmed"
        assert conf_data["dataset_mapping"]["confirmation"]["confirmer_ref"] == "analista_datos"

    def test_7_reject_obsolete_version(self, tmp_path):
        client, _, _ = _setup_api(tmp_path)
        project_id = _create_project(client)
        vars_, dims, inds, items, rules = _sample_structure()
        create_resp = client.post(
            f"/api/research/projects/{project_id}/instruments",
            json={
                "variables": [v.model_dump(mode="json") for v in vars_],
                "dimensions": [d.model_dump(mode="json") for d in dims],
                "indicators": [i.model_dump(mode="json") for i in inds],
                "items": [it.model_dump(mode="json") for it in items],
                "scoring_rules": [r.model_dump(mode="json") for r in rules],
            },
        )
        inst_id = create_resp.json()["instrument_id"]

        # Avanzar versión a 1
        client.put(
            f"/api/research/projects/{project_id}/instruments/{inst_id}",
            json={
                "expected_version": 0,
                "variables": [v.model_dump(mode="json") for v in vars_],
                "dimensions": [d.model_dump(mode="json") for d in dims],
                "indicators": [i.model_dump(mode="json") for i in inds],
                "items": [it.model_dump(mode="json") for it in items],
                "scoring_rules": [r.model_dump(mode="json") for r in rules],
            },
        )

        # Intentar actualizar con expected_version=0 obsoleto
        put_bad = client.put(
            f"/api/research/projects/{project_id}/instruments/{inst_id}",
            json={
                "expected_version": 0,
                "variables": [v.model_dump(mode="json") for v in vars_],
                "dimensions": [d.model_dump(mode="json") for d in dims],
                "indicators": [i.model_dump(mode="json") for i in inds],
                "items": [it.model_dump(mode="json") for it in items],
                "scoring_rules": [r.model_dump(mode="json") for r in rules],
            },
        )
        assert put_bad.status_code == 409
        assert "Conflicto de concurrencia" in put_bad.json()["detail"]

    def test_8_reject_incomplete_confirmation(self, tmp_path):
        client, _, _ = _setup_api(tmp_path)
        project_id = _create_project(client)
        vars_, dims, inds, items, rules = _sample_structure()

        # Regla NO confirmada
        rules[0].confirmed = False

        create_resp = client.post(
            f"/api/research/projects/{project_id}/instruments",
            json={
                "variables": [v.model_dump(mode="json") for v in vars_],
                "dimensions": [d.model_dump(mode="json") for d in dims],
                "indicators": [i.model_dump(mode="json") for i in inds],
                "items": [it.model_dump(mode="json") for it in items],
                "scoring_rules": [r.model_dump(mode="json") for r in rules],
            },
        )
        inst_id = create_resp.json()["instrument_id"]

        # 1. Confirmar sin haber vinculado metodología
        conf_bad = client.post(
            f"/api/research/projects/{project_id}/instruments/{inst_id}/confirm",
            json={"expected_version": 0, "confirmer_ref": "metodologo"},
        )
        assert conf_bad.status_code == 422
        assert "procedencia metodológica" in conf_bad.json()["detail"]

        # 2. Vincular metodología pero intentar confirmar con reglas pendientes
        doc_id = _upload_document_and_review(client, project_id, vars_[0].variable_id)
        client.post(
            f"/api/research/projects/{project_id}/instruments/{inst_id}/methodology",
            json={"expected_version": 0, "document_id": doc_id},
        )
        conf_bad_rules = client.post(
            f"/api/research/projects/{project_id}/instruments/{inst_id}/confirm",
            json={"expected_version": 1, "confirmer_ref": "metodologo"},
        )
        assert conf_bad_rules.status_code == 422
        assert "pendientes de confirmación explícita" in conf_bad_rules.json()["detail"]

    def test_9_reject_instrument_cross_project(self, tmp_path):
        client, _, _ = _setup_api(tmp_path)
        proj1_id = _create_project(client)
        proj2_id = _create_project(client)
        vars_, dims, inds, items, rules = _sample_structure()

        create_resp = client.post(
            f"/api/research/projects/{proj1_id}/instruments",
            json={
                "variables": [v.model_dump(mode="json") for v in vars_],
                "dimensions": [d.model_dump(mode="json") for d in dims],
                "indicators": [i.model_dump(mode="json") for i in inds],
                "items": [it.model_dump(mode="json") for it in items],
                "scoring_rules": [r.model_dump(mode="json") for r in rules],
            },
        )
        inst1_id = create_resp.json()["instrument_id"]

        # Intentar acceder al instrumento de proj1 usando la URL de proj2
        cross_resp = client.get(f"/api/research/projects/{proj2_id}/instruments/{inst1_id}")
        assert cross_resp.status_code == 404

    def test_10_detect_stale_when_methodology_changes(self, tmp_path):
        client, _, app = _setup_api(tmp_path)
        project_id = _create_project(client)
        vars_, dims, inds, items, rules = _sample_structure()
        doc_id = _upload_document_and_review(client, project_id, vars_[0].variable_id)
        rules[0].confirmed = True

        create_resp = client.post(
            f"/api/research/projects/{project_id}/instruments",
            json={
                "variables": [v.model_dump(mode="json") for v in vars_],
                "dimensions": [d.model_dump(mode="json") for d in dims],
                "indicators": [i.model_dump(mode="json") for i in inds],
                "items": [it.model_dump(mode="json") for it in items],
                "scoring_rules": [r.model_dump(mode="json") for r in rules],
            },
        )
        inst_id = create_resp.json()["instrument_id"]

        client.post(
            f"/api/research/projects/{project_id}/instruments/{inst_id}/methodology",
            json={"expected_version": 0, "document_id": doc_id},
        )
        client.post(
            f"/api/research/projects/{project_id}/instruments/{inst_id}/confirm",
            json={"expected_version": 1, "confirmer_ref": "metodologo"},
        )

        # Modificar metodología con nuevo título
        rev_url = f"/api/research/projects/{project_id}/documents/{doc_id}/methodology/review"
        rev_data = client.get(rev_url).json()
        rev_data["content"]["title"]["value"] = "Metodología Totalmente Alterada"
        client.put(rev_url, json={"version": 1, "content": rev_data["content"]})
        client.post(rev_url + "/confirm", json={"version": 2})

        # Al consultar via reader interno, debe levantar InstrumentStaleError
        reader = app.state.instrument_reader
        with pytest.raises(InstrumentStaleError):
            reader.get_confirmed_context(project_id, inst_id)

    def test_11_detect_stale_when_dataset_changes(self, tmp_path):
        client, _, app = _setup_api(tmp_path)
        project_id = _create_project(client)
        vars_, dims, inds, items, rules = _sample_structure()
        doc_id = _upload_document_and_review(client, project_id, vars_[0].variable_id)
        dataset_id = _upload_dataset(client, project_id, b"p1,p2\n1,2\n")
        rules[0].confirmed = True

        create_resp = client.post(
            f"/api/research/projects/{project_id}/instruments",
            json={
                "variables": [v.model_dump(mode="json") for v in vars_],
                "dimensions": [d.model_dump(mode="json") for d in dims],
                "indicators": [i.model_dump(mode="json") for i in inds],
                "items": [it.model_dump(mode="json") for it in items],
                "scoring_rules": [r.model_dump(mode="json") for r in rules],
            },
        )
        inst_id = create_resp.json()["instrument_id"]

        client.post(
            f"/api/research/projects/{project_id}/instruments/{inst_id}/methodology",
            json={"expected_version": 0, "document_id": doc_id},
        )
        client.post(
            f"/api/research/projects/{project_id}/instruments/{inst_id}/mapping",
            json={
                "expected_version": 1,
                "dataset_id": dataset_id,
                "item_columns": [
                    {"item_id": str(items[0].item_id), "column_name": "p1"},
                    {"item_id": str(items[1].item_id), "column_name": "p2"},
                ],
            },
        )
        client.post(
            f"/api/research/projects/{project_id}/instruments/{inst_id}/mapping/confirm",
            json={"expected_version": 2, "confirmer_ref": "analista"},
        )
        client.post(
            f"/api/research/projects/{project_id}/instruments/{inst_id}/confirm",
            json={"expected_version": 3, "confirmer_ref": "metodologo"},
        )

        # Alterar físicamente el archivo del dataset
        service = app.state.instrument_service
        raw_path = service.datasets.repository._path(UUID(dataset_id))
        raw_path.write_bytes(b"p1,p2\n999,888\n")

        # Reader interno debe detectar desactualización del dataset
        reader = app.state.instrument_reader
        with pytest.raises(InstrumentStaleError) as exc_info:
            reader.get_confirmed_context(project_id, inst_id)
        assert any("dataset" in r.lower() for r in exc_info.value.reasons)

    def test_12_persistence_after_app_restart(self, tmp_path):
        client, settings, _ = _setup_api(tmp_path)
        project_id = _create_project(client)
        vars_, dims, inds, items, rules = _sample_structure()

        create_resp = client.post(
            f"/api/research/projects/{project_id}/instruments",
            json={
                "variables": [v.model_dump(mode="json") for v in vars_],
                "dimensions": [d.model_dump(mode="json") for d in dims],
                "indicators": [i.model_dump(mode="json") for i in inds],
                "items": [it.model_dump(mode="json") for it in items],
                "scoring_rules": [r.model_dump(mode="json") for r in rules],
            },
        )
        inst_id = create_resp.json()["instrument_id"]

        # Simular reinicio completo creando nueva aplicación y cliente apuntando al mismo disco
        new_app = create_app(settings=settings)
        new_client = TestClient(new_app)

        get_resp = new_client.get(f"/api/research/projects/{project_id}/instruments/{inst_id}")
        assert get_resp.status_code == 200
        assert get_resp.json()["instrument_id"] == inst_id
        assert get_resp.json()["status"] == "draft"
        assert len(get_resp.json()["items"]) == 2

    def test_13_version_history_preservation(self, tmp_path):
        client, _, _ = _setup_api(tmp_path)
        project_id = _create_project(client)
        vars_, dims, inds, items, rules = _sample_structure()
        doc_id = _upload_document_and_review(client, project_id, vars_[0].variable_id)
        rules[0].confirmed = True

        create_resp = client.post(
            f"/api/research/projects/{project_id}/instruments",
            json={
                "variables": [v.model_dump(mode="json") for v in vars_],
                "dimensions": [d.model_dump(mode="json") for d in dims],
                "indicators": [i.model_dump(mode="json") for i in inds],
                "items": [it.model_dump(mode="json") for it in items],
                "scoring_rules": [r.model_dump(mode="json") for r in rules],
            },
        )
        inst_id = create_resp.json()["instrument_id"]

        client.post(
            f"/api/research/projects/{project_id}/instruments/{inst_id}/methodology",
            json={"expected_version": 0, "document_id": doc_id},
        )
        client.post(
            f"/api/research/projects/{project_id}/instruments/{inst_id}/confirm",
            json={"expected_version": 1, "confirmer_ref": "metodologo"},
        )

        hist_resp = client.get(f"/api/research/projects/{project_id}/instruments/{inst_id}/history")
        assert hist_resp.status_code == 200
        history = hist_resp.json()
        assert len(history) == 3
        assert [h["version"] for h in history] == [0, 1, 2]
        assert history[0]["status"] == "draft"
        assert history[2]["status"] == "reviewed"

        # Recuperar v0 mediante query param version=0
        v0_resp = client.get(f"/api/research/projects/{project_id}/instruments/{inst_id}?version=0")
        assert v0_resp.status_code == 200
        assert v0_resp.json()["version"] == 0
        assert v0_resp.json()["status"] == "draft"

    def test_14_original_dataset_never_modified_by_api(self, tmp_path):
        client, _, _ = _setup_api(tmp_path)
        project_id = _create_project(client)
        vars_, dims, inds, items, rules = _sample_structure()
        original_bytes = b"p1,p2,extra\n10,20,alpha\n30,40,beta\n"
        dataset_id = _upload_dataset(client, project_id, original_bytes)

        create_resp = client.post(
            f"/api/research/projects/{project_id}/instruments",
            json={
                "variables": [v.model_dump(mode="json") for v in vars_],
                "dimensions": [d.model_dump(mode="json") for d in dims],
                "indicators": [i.model_dump(mode="json") for i in inds],
                "items": [it.model_dump(mode="json") for it in items],
                "scoring_rules": [r.model_dump(mode="json") for r in rules],
            },
        )
        inst_id = create_resp.json()["instrument_id"]

        client.post(
            f"/api/research/projects/{project_id}/instruments/{inst_id}/mapping",
            json={
                "expected_version": 0,
                "dataset_id": dataset_id,
                "item_columns": [
                    {"item_id": str(items[0].item_id), "column_name": "p1"},
                    {"item_id": str(items[1].item_id), "column_name": "p2"},
                ],
            },
        )

        # Consultar preview del dataset por su ruta original
        ds_resp = client.get(f"/api/research/projects/{project_id}/datasets/{dataset_id}/preview")
        assert ds_resp.status_code == 200
        assert ds_resp.json()["columns"] == ["p1", "p2", "extra"]

    def test_15_api_rejects_individual_responses_and_extra_fields(self, tmp_path):
        client, _, _ = _setup_api(tmp_path)
        project_id = _create_project(client)
        vars_, dims, inds, items, rules = _sample_structure()

        body_with_individual_data = {
            "variables": [v.model_dump(mode="json") for v in vars_],
            "dimensions": [d.model_dump(mode="json") for d in dims],
            "indicators": [i.model_dump(mode="json") for i in inds],
            "items": [it.model_dump(mode="json") for it in items],
            "scoring_rules": [r.model_dump(mode="json") for r in rules],
            "survey_responses": [{"student_id": "12345", "q1": 5, "name": "Juan Perez"}],
        }
        resp = client.post(
            f"/api/research/projects/{project_id}/instruments",
            json=body_with_individual_data,
        )
        assert resp.status_code == 422
        assert "extra_forbidden" in resp.text or "no está permitido" in resp.text

    def test_16_confirm_scoring_rules_endpoint(self, tmp_path):
        """Verifica el endpoint para confirmar explícitamente reglas de puntuación."""
        client, _, _ = _setup_api(tmp_path)
        project_id = _create_project(client)
        vars_, dims, inds, items, rules = _sample_structure()
        assert rules[0].confirmed is False

        create_resp = client.post(
            f"/api/research/projects/{project_id}/instruments",
            json={
                "variables": [v.model_dump(mode="json") for v in vars_],
                "dimensions": [d.model_dump(mode="json") for d in dims],
                "indicators": [i.model_dump(mode="json") for i in inds],
                "items": [it.model_dump(mode="json") for it in items],
                "scoring_rules": [r.model_dump(mode="json") for r in rules],
            },
        )
        inst_id = create_resp.json()["instrument_id"]

        # Confirmar regla específica
        conf_resp = client.post(
            f"/api/research/projects/{project_id}/instruments/{inst_id}/rules/confirm",
            json={
                "expected_version": 0,
                "rule_ids": [str(rules[0].scoring_rule_id)],
            },
        )
        assert conf_resp.status_code == 200
        assert conf_resp.json()["version"] == 1
        assert conf_resp.json()["scoring_rules"][0]["confirmed"] is True

    def test_17_mark_stale_endpoint(self, tmp_path):
        """Verifica la materialización transaccional de stale vía endpoint."""
        client, _, _ = _setup_api(tmp_path)
        project_id = _create_project(client)
        vars_, dims, inds, items, rules = _sample_structure()
        doc_id = _upload_document_and_review(client, project_id, vars_[0].variable_id)
        rules[0].confirmed = True

        create_resp = client.post(
            f"/api/research/projects/{project_id}/instruments",
            json={
                "variables": [v.model_dump(mode="json") for v in vars_],
                "dimensions": [d.model_dump(mode="json") for d in dims],
                "indicators": [i.model_dump(mode="json") for i in inds],
                "items": [it.model_dump(mode="json") for it in items],
                "scoring_rules": [r.model_dump(mode="json") for r in rules],
            },
        )
        inst_id = create_resp.json()["instrument_id"]

        client.post(
            f"/api/research/projects/{project_id}/instruments/{inst_id}/methodology",
            json={"expected_version": 0, "document_id": doc_id},
        )
        client.post(
            f"/api/research/projects/{project_id}/instruments/{inst_id}/confirm",
            json={"expected_version": 1, "confirmer_ref": "metodologo"},
        )

        # Modificar metodología
        rev_url = f"/api/research/projects/{project_id}/documents/{doc_id}/methodology/review"
        rev_data = client.get(rev_url).json()
        rev_data["content"]["title"]["value"] = "Titulo Alterado"
        client.put(rev_url, json={"version": 1, "content": rev_data["content"]})
        client.post(rev_url + "/confirm", json={"version": 2})

        # Materializar stale
        stale_resp = client.post(
            f"/api/research/projects/{project_id}/instruments/{inst_id}/mark-stale",
            json={"expected_version": 2},
        )
        assert stale_resp.status_code == 200
        assert stale_resp.json()["version"] == 3
        assert stale_resp.json()["status"] == "stale"

    def test_18_link_methodology_with_variable_links(self, tmp_path):
        """Verifica vinculación metodológica con correspondencia explícita variable_links."""
        client, _, _ = _setup_api(tmp_path)
        project_id = _create_project(client)
        vars_, dims, inds, items, rules = _sample_structure()
        # Variable no vinculada inicialmente
        vars_[0].methodology_variable_id = None
        doc_id = _upload_document_and_review(client, project_id, uuid4())

        create_resp = client.post(
            f"/api/research/projects/{project_id}/instruments",
            json={
                "variables": [v.model_dump(mode="json") for v in vars_],
                "dimensions": [d.model_dump(mode="json") for d in dims],
                "indicators": [i.model_dump(mode="json") for i in inds],
                "items": [it.model_dump(mode="json") for it in items],
                "scoring_rules": [r.model_dump(mode="json") for r in rules],
            },
        )
        inst_id = create_resp.json()["instrument_id"]

        # Sin variable_links debe fallar porque methodology_variable_id es None
        fail_resp = client.post(
            f"/api/research/projects/{project_id}/instruments/{inst_id}/methodology",
            json={"expected_version": 0, "document_id": doc_id},
        )
        assert fail_resp.status_code == 422
        assert "no tiene una correspondencia metodológica" in fail_resp.json()["detail"]

        # Con variable_links debe tener éxito
        rev_url = f"/api/research/projects/{project_id}/documents/{doc_id}/methodology/review"
        rev_var_id = client.get(rev_url).json()["content"]["variables"][0]["id"]

        succ_resp = client.post(
            f"/api/research/projects/{project_id}/instruments/{inst_id}/methodology",
            json={
                "expected_version": 0,
                "document_id": doc_id,
                "variable_links": {str(vars_[0].variable_id): rev_var_id},
            },
        )
        assert succ_resp.status_code == 200
        assert succ_resp.json()["variables"][0]["methodology_variable_id"] == rev_var_id

    def test_19_update_draft_invalidates_mapping_endpoint(self, tmp_path):
        """Verifica que actualizar borrador invalida el mapeo confirmado a nivel de API."""
        client, _, _ = _setup_api(tmp_path)
        project_id = _create_project(client)
        vars_, dims, inds, items, rules = _sample_structure()
        dataset_id = _upload_dataset(client, project_id)

        create_resp = client.post(
            f"/api/research/projects/{project_id}/instruments",
            json={
                "variables": [v.model_dump(mode="json") for v in vars_],
                "dimensions": [d.model_dump(mode="json") for d in dims],
                "indicators": [i.model_dump(mode="json") for i in inds],
                "items": [it.model_dump(mode="json") for it in items],
                "scoring_rules": [r.model_dump(mode="json") for r in rules],
            },
        )
        inst_id = create_resp.json()["instrument_id"]

        client.post(
            f"/api/research/projects/{project_id}/instruments/{inst_id}/mapping",
            json={
                "expected_version": 0,
                "dataset_id": dataset_id,
                "item_columns": [
                    {"item_id": str(items[0].item_id), "column_name": "p1"},
                    {"item_id": str(items[1].item_id), "column_name": "p2"},
                ],
            },
        )
        client.post(
            f"/api/research/projects/{project_id}/instruments/{inst_id}/mapping/confirm",
            json={"expected_version": 1, "confirmer_ref": "analista"},
        )

        # Actualizar borrador modificando el texto del ítem
        items[0].text = "Texto modificado del ítem 1"
        put_resp = client.put(
            f"/api/research/projects/{project_id}/instruments/{inst_id}",
            json={
                "expected_version": 2,
                "variables": [v.model_dump(mode="json") for v in vars_],
                "dimensions": [d.model_dump(mode="json") for d in dims],
                "indicators": [i.model_dump(mode="json") for i in inds],
                "items": [it.model_dump(mode="json") for it in items],
                "scoring_rules": [r.model_dump(mode="json") for r in rules],
            },
        )
        assert put_resp.status_code == 200
        data = put_resp.json()
        assert data["version"] == 3
        assert data["dataset_mapping"]["status"] == "draft"
        assert data["dataset_mapping"]["confirmation"]["state"] == "pending"
        assert data["dataset_mapping"]["instrument_version"] == 3
