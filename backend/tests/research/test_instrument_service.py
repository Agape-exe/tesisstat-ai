"""Comprehensive tests for InstrumentService, SQLite persistence, staleness, and reader port."""

from contextlib import closing
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from app.modules.research.datasets.models import Dataset, DatasetPreview
from app.modules.research.datasets.sqlite_repository import SQLiteDatasetRepository
from app.modules.research.datasets.use_cases import DatasetService
from app.modules.research.documents.models import Document
from app.modules.research.documents.sqlite_repository import SQLiteDocumentRepository
from app.modules.research.documents.use_cases import DocumentService
from app.modules.research.instrument.fixtures import (
    build_deterministic_confirmed_instrument_with_mapping,
    build_deterministic_reviewed_instrument_without_mapping,
    create_deterministic_harness,
    deterministic_uuid,
    standard_likert_options,
)
from app.modules.research.instrument.models import (
    InstrumentDimension,
    InstrumentIndicator,
    InstrumentItem,
    InstrumentVariable,
    ItemColumnMapping,
    ScoringRule,
)
from app.modules.research.instrument.reader import (
    ResearchInstrumentContextReader,
)
from app.modules.research.instrument.repository import (
    InstrumentConflict,
    InstrumentNotConfirmedError,
    InstrumentNotFound,
    InstrumentStaleError,
    InstrumentValidationError,
)
from app.modules.research.instrument.service import InstrumentService
from app.modules.research.instrument.sqlite_repository import SQLiteInstrumentRepository
from app.modules.research.methodology.models import (
    MethodologyReview,
    ReviewContent,
    ReviewFinding,
    ReviewVariable,
)
from app.modules.research.methodology.sqlite_repository import SQLiteMethodologyRepository
from app.modules.research.projects.models import ProjectDraft
from app.modules.research.projects.sqlite_repository import SQLiteProjectRepository
from app.modules.research.projects.use_cases import ProjectService
from app.shared.instrument_contracts import InstrumentContext


def _create_harness(tmp_path):
    db_path = tmp_path / "research.db"
    storage_path = tmp_path / "storage"
    storage_path.mkdir(parents=True, exist_ok=True)

    project_repo = SQLiteProjectRepository(db_path)
    projects = ProjectService(project_repo)

    doc_repo = SQLiteDocumentRepository(db_path, storage_path / "docs")
    documents = DocumentService(doc_repo, projects)

    dataset_repo = SQLiteDatasetRepository(db_path, storage_path / "datasets")
    datasets = DatasetService(dataset_repo, projects)

    methodology_repo = SQLiteMethodologyRepository(db_path)

    instrument_repo = SQLiteInstrumentRepository(db_path)
    service = InstrumentService(
        repository=instrument_repo,
        projects=projects,
        documents=documents,
        methodology=methodology_repo,
        datasets=datasets,
    )
    reader = ResearchInstrumentContextReader(service)

    return {
        "db_path": db_path,
        "storage_path": storage_path,
        "projects": projects,
        "documents": documents,
        "datasets": datasets,
        "methodology": methodology_repo,
        "instrument_repo": instrument_repo,
        "service": service,
        "reader": reader,
    }


def _seed_project(harness):
    draft = ProjectDraft(
        title="Investigación de Clima y Desempeño",
        university="Universidad Nacional",
        program="Psicología Organizacional",
        degree="bachelor",
    )
    return harness["projects"].create(draft)


def _seed_document(harness, project_id: UUID, content: bytes = b"%PDF-1.4\nCuestionario\n%%EOF"):
    doc = Document(
        id=uuid4(),
        project_id=project_id,
        name="instrumento.pdf",
        format="pdf",
        size=len(content),
        uploaded_at=datetime.now(UTC),
    )
    harness["documents"].repository.add(doc, content)
    return doc


def _seed_methodology_review(harness, project_id: UUID, document_id: UUID, var_id: UUID):
    finding = ReviewFinding(value="Clima", kind="quotation", evidence=["Texto fuente"])
    review = MethodologyReview(
        project_id=project_id,
        document_id=document_id,
        origin="manual",
        content=ReviewContent(
            title=ReviewFinding(value="Investigación", kind="manual"),
            variables=[
                ReviewVariable(
                    id=var_id,
                    name=finding,
                )
            ],
        ),
        pending_fields=[],
        review_status="reviewed",
        version=1,
        updated_at=datetime.now(UTC),
        reviewed_at=datetime.now(UTC),
    )
    harness["methodology"].save_review(review, expected_version=None)
    return review


def _seed_dataset(harness, project_id: UUID, data: bytes = b"p1,p2,extra\n1,5,abc\n2,4,def\n"):
    dataset = Dataset(
        id=uuid4(),
        project_id=project_id,
        name="datos.csv",
        format="csv",
        size=len(data),
        row_count=2,
        column_count=3,
        columns=["p1", "p2", "extra"],
        uploaded_at=datetime.now(UTC),
        active=True,
    )
    preview = DatasetPreview(
        columns=["p1", "p2", "extra"],
        rows=[["1", "5", "abc"], ["2", "4", "def"]],
        row_count=2,
        column_count=3,
        format="csv",
        warnings=[],
    )
    harness["datasets"].repository.add(dataset, preview, data)
    harness["datasets"].repository.activate(project_id, dataset.id)
    return dataset


def _sample_structure(var_id: UUID | None = None):
    v_id = var_id or uuid4()
    dim_id = uuid4()
    ind_id = uuid4()
    it1_id = uuid4()
    it2_id = uuid4()

    variables = [
        InstrumentVariable(
            variable_id=v_id,
            name="Clima Laboral",
            scale="ordinal",
            methodology_variable_id=v_id,
        )
    ]
    dimensions = [
        InstrumentDimension(
            dimension_id=dim_id,
            variable_id=v_id,
            name="Comunicación",
        )
    ]
    indicators = [
        InstrumentIndicator(
            indicator_id=ind_id,
            dimension_id=dim_id,
            name="Claridad",
        )
    ]
    items = [
        InstrumentItem(
            item_id=it1_id,
            variable_id=v_id,
            dimension_id=dim_id,
            indicator_id=ind_id,
            text="La comunicación es clara.",
            response_type="single_choice",
            response_options=standard_likert_options(),
            valid_min=1.0,
            valid_max=5.0,
        ),
        InstrumentItem(
            item_id=it2_id,
            variable_id=v_id,
            dimension_id=dim_id,
            indicator_id=ind_id,
            text="La información es confusa.",
            response_type="single_choice",
            response_options=standard_likert_options(),
            valid_min=1.0,
            valid_max=5.0,
            reverse_scored=True,
            reverse_rule="min_plus_max_minus_value",
        ),
    ]
    scoring_rules = [
        ScoringRule(
            scoring_rule_id=uuid4(),
            scope="dimension",
            dimension_id=dim_id,
            item_ids=[it1_id, it2_id],
            aggregation="sum",
            missing_policy="all_required",
            confirmed=False,
        )
    ]
    return variables, dimensions, indicators, items, scoring_rules


class TestInstrumentServiceAndPersistence:
    def test_create_and_retrieve_instrument(self, tmp_path):
        h = _create_harness(tmp_path)
        proj = _seed_project(h)
        vars_, dims, inds, items, rules = _sample_structure()

        inst = h["service"].create_draft(
            project_id=proj.id,
            variables=vars_,
            dimensions=dims,
            indicators=inds,
            items=items,
            scoring_rules=rules,
        )

        assert inst.version == 0
        assert inst.status == "draft"
        assert inst.confirmation.state == "pending"

        retrieved = h["service"].get(proj.id, inst.instrument_id)
        assert retrieved.instrument_id == inst.instrument_id
        assert len(retrieved.items) == 2
        assert retrieved.items[0].text == "La comunicación es clara."

    def test_persistence_after_service_reboot(self, tmp_path):
        h = _create_harness(tmp_path)
        proj = _seed_project(h)
        vars_, dims, inds, items, rules = _sample_structure()
        inst = h["service"].create_draft(
            project_id=proj.id,
            variables=vars_,
            dimensions=dims,
            indicators=inds,
            items=items,
            scoring_rules=rules,
        )

        # Simular reinicio creando nueva instancia de repositorio y servicio
        # apuntando al mismo archivo SQLite
        new_repo = SQLiteInstrumentRepository(h["db_path"])
        new_service = InstrumentService(
            repository=new_repo,
            projects=h["projects"],
            documents=h["documents"],
            methodology=h["methodology"],
            datasets=h["datasets"],
        )

        retrieved = new_service.get(proj.id, inst.instrument_id)
        assert retrieved.instrument_id == inst.instrument_id
        assert retrieved.version == 0
        assert len(retrieved.variables) == 1

    def test_update_draft_with_expected_version(self, tmp_path):
        h = _create_harness(tmp_path)
        proj = _seed_project(h)
        vars_, dims, inds, items, rules = _sample_structure()
        inst = h["service"].create_draft(proj.id, vars_, dims, inds, items, rules)

        # Actualización versión 0 -> 1 con regla correspondiente al ítem 0
        rule_single = rules[0].model_copy(update={"item_ids": [items[0].item_id]})
        updated1 = h["service"].update_draft(
            project_id=proj.id,
            instrument_id=inst.instrument_id,
            expected_version=0,
            items=items[:1],
            scoring_rules=[rule_single],
        )
        assert updated1.version == 1
        assert len(updated1.items) == 1

        # Actualización versión 1 -> 2
        updated2 = h["service"].update_draft(
            project_id=proj.id,
            instrument_id=inst.instrument_id,
            expected_version=1,
            items=items,
            scoring_rules=rules,
        )
        assert updated2.version == 2
        assert len(updated2.items) == 2

    def test_update_draft_with_obsolete_version_fails(self, tmp_path):
        h = _create_harness(tmp_path)
        proj = _seed_project(h)
        vars_, dims, inds, items, rules = _sample_structure()
        inst = h["service"].create_draft(proj.id, vars_, dims, inds, items, rules)

        # Actualiza a versión 1
        h["service"].update_draft(proj.id, inst.instrument_id, expected_version=0, items=items)

        # Intento con versión 0 obsoleta
        with pytest.raises(InstrumentConflict) as exc:
            h["service"].update_draft(proj.id, inst.instrument_id, expected_version=0, items=items)
        assert "no coincide con la versión actual persistida" in str(exc.value)

    def test_concurrency_conflict(self, tmp_path):
        h = _create_harness(tmp_path)
        proj = _seed_project(h)
        vars_, dims, inds, items, rules = _sample_structure()
        inst = h["service"].create_draft(proj.id, vars_, dims, inds, items, rules)

        # Ambos procesos leen la versión 0
        h["service"].update_draft(proj.id, inst.instrument_id, expected_version=0, items=items)

        # El segundo proceso intenta actualizar esperando 0 cuando ya es 1
        with pytest.raises(InstrumentConflict):
            h["service"].update_draft(proj.id, inst.instrument_id, expected_version=0, items=items)

    def test_link_methodology_and_confirm_instrument(self, tmp_path):
        h = _create_harness(tmp_path)
        proj = _seed_project(h)
        doc = _seed_document(h, proj.id)
        vars_, dims, inds, items, rules = _sample_structure()

        _seed_methodology_review(h, proj.id, doc.id, vars_[0].variable_id)

        inst = h["service"].create_draft(proj.id, vars_, dims, inds, items, rules)

        # Vincular metodología
        linked = h["service"].link_methodology(
            project_id=proj.id,
            instrument_id=inst.instrument_id,
            expected_version=0,
            document_id=doc.id,
        )
        assert linked.version == 1
        assert linked.provenance is not None
        assert linked.provenance.methodology_review_id == doc.id

        # Confirmar instrumento sin confirmar reglas debe fallar
        with pytest.raises(InstrumentValidationError) as exc:
            h["service"].confirm_instrument(
                project_id=proj.id,
                instrument_id=inst.instrument_id,
                expected_version=1,
                confirmer_ref="revisor_docente",
            )
        assert "pendientes de confirmación explícita" in str(exc.value)

        # Confirmación explícita de reglas de puntuación
        rules_conf = h["service"].confirm_scoring_rules(
            project_id=proj.id,
            instrument_id=inst.instrument_id,
            expected_version=1,
        )
        assert rules_conf.version == 2
        assert rules_conf.scoring_rules[0].confirmed is True

        # Confirmar instrumento
        confirmed = h["service"].confirm_instrument(
            project_id=proj.id,
            instrument_id=inst.instrument_id,
            expected_version=2,
            confirmer_ref="revisor_docente",
        )
        assert confirmed.version == 3
        assert confirmed.status == "reviewed"
        assert confirmed.confirmation.state == "confirmed"
        assert confirmed.scoring_rules[0].confirmed is True

    def test_confirm_instrument_idempotency(self, tmp_path):
        h = _create_harness(tmp_path)
        proj = _seed_project(h)
        doc = _seed_document(h, proj.id)
        vars_, dims, inds, items, rules = _sample_structure()
        _seed_methodology_review(h, proj.id, doc.id, vars_[0].variable_id)
        inst = h["service"].create_draft(proj.id, vars_, dims, inds, items, rules)
        linked = h["service"].link_methodology(proj.id, inst.instrument_id, 0, doc.id)
        rules_conf = h["service"].confirm_scoring_rules(proj.id, inst.instrument_id, linked.version)
        confirmed = h["service"].confirm_instrument(
            proj.id, inst.instrument_id, rules_conf.version, "rev"
        )

        # Repetición idempotente
        idem = h["instrument_repo"].update(confirmed, expected_version=confirmed.version)
        assert idem.version == confirmed.version
        assert idem.status == "reviewed"

    def test_dataset_mapping_and_confirmation(self, tmp_path):
        h = _create_harness(tmp_path)
        proj = _seed_project(h)
        doc = _seed_document(h, proj.id)
        dataset = _seed_dataset(h, proj.id)
        vars_, dims, inds, items, rules = _sample_structure()
        _seed_methodology_review(h, proj.id, doc.id, vars_[0].variable_id)

        inst = h["service"].create_draft(proj.id, vars_, dims, inds, items, rules)
        linked = h["service"].link_methodology(proj.id, inst.instrument_id, 0, doc.id)

        # Mapear columnas 1:1
        mapping_cols = [
            ItemColumnMapping(item_id=items[0].item_id, column_name="p1"),
            ItemColumnMapping(item_id=items[1].item_id, column_name="p2"),
        ]
        mapped = h["service"].set_mapping(
            project_id=proj.id,
            instrument_id=inst.instrument_id,
            expected_version=linked.version,
            dataset_id=dataset.id,
            item_columns=mapping_cols,
        )
        assert mapped.dataset_mapping is not None
        assert mapped.dataset_mapping.status == "draft"

        # Confirmar mapeo
        confirmed_map = h["service"].confirm_mapping(
            project_id=proj.id,
            instrument_id=inst.instrument_id,
            expected_version=mapped.version,
            confirmer_ref="revisor_datos",
        )
        assert confirmed_map.dataset_mapping.status == "confirmed"
        assert confirmed_map.dataset_mapping.confirmation.state == "confirmed"

    def test_mapping_rejects_missing_column_and_incomplete_coverage(self, tmp_path):
        h = _create_harness(tmp_path)
        proj = _seed_project(h)
        dataset = _seed_dataset(h, proj.id)
        vars_, dims, inds, items, rules = _sample_structure()
        inst = h["service"].create_draft(proj.id, vars_, dims, inds, items, rules)

        # Columna no existe en dataset
        with pytest.raises(InstrumentValidationError) as exc:
            h["service"].set_mapping(
                proj.id,
                inst.instrument_id,
                0,
                dataset.id,
                [ItemColumnMapping(item_id=items[0].item_id, column_name="columna_fantasma")],
            )
        assert "no existe en el dataset" in str(exc.value)

        # Mapeo incompleto no se puede confirmar
        mapped_one = h["service"].set_mapping(
            proj.id,
            inst.instrument_id,
            0,
            dataset.id,
            [ItemColumnMapping(item_id=items[0].item_id, column_name="p1")],
        )
        with pytest.raises(InstrumentValidationError) as exc2:
            h["service"].confirm_mapping(proj.id, inst.instrument_id, mapped_one.version, "rev")
        assert "cubrir el 100% de los ítems" in str(exc2.value)

    def test_staleness_detection_when_methodology_changes(self, tmp_path):
        h = _create_harness(tmp_path)
        proj = _seed_project(h)
        doc = _seed_document(h, proj.id)
        vars_, dims, inds, items, rules = _sample_structure()
        review = _seed_methodology_review(h, proj.id, doc.id, vars_[0].variable_id)

        inst = h["service"].create_draft(proj.id, vars_, dims, inds, items, rules)
        linked = h["service"].link_methodology(proj.id, inst.instrument_id, 0, doc.id)
        rules_conf = h["service"].confirm_scoring_rules(proj.id, inst.instrument_id, linked.version)
        confirmed = h["service"].confirm_instrument(
            proj.id, inst.instrument_id, rules_conf.version, "rev"
        )

        # Inicialmente no está stale
        is_stale, _ = h["service"].check_stale(proj.id, confirmed.instrument_id)
        assert is_stale is False

        # Se modifica la metodología aumentando su versión
        updated_review = review.model_copy(
            update={
                "version": 2,
                "content": ReviewContent(
                    title=ReviewFinding(value="Título Modificado", kind="manual"),
                    variables=review.content.variables,
                ),
            }
        )
        h["methodology"].save_review(updated_review, expected_version=1)

        # Detección de stale
        is_stale_after, reasons = h["service"].check_stale(proj.id, confirmed.instrument_id)
        assert is_stale_after is True
        assert any("metodología ha cambiado" in r for r in reasons)

    def test_staleness_detection_when_dataset_changes(self, tmp_path):
        h = _create_harness(tmp_path)
        proj = _seed_project(h)
        doc = _seed_document(h, proj.id)
        dataset = _seed_dataset(h, proj.id)
        vars_, dims, inds, items, rules = _sample_structure()
        _seed_methodology_review(h, proj.id, doc.id, vars_[0].variable_id)

        inst = h["service"].create_draft(proj.id, vars_, dims, inds, items, rules)
        linked = h["service"].link_methodology(proj.id, inst.instrument_id, 0, doc.id)
        mapping_cols = [
            ItemColumnMapping(item_id=items[0].item_id, column_name="p1"),
            ItemColumnMapping(item_id=items[1].item_id, column_name="p2"),
        ]
        mapped = h["service"].set_mapping(
            proj.id, inst.instrument_id, linked.version, dataset.id, mapping_cols
        )
        h["service"].confirm_mapping(proj.id, inst.instrument_id, mapped.version, "rev")

        # Modificar archivo del dataset en disco
        storage_file = h["storage_path"] / "datasets" / dataset.id.hex
        storage_file.write_bytes(b"p1,p2,extra\n99,99,zzz\n")

        # Staleness detectado
        is_stale, reasons = h["service"].check_stale(proj.id, inst.instrument_id)
        assert is_stale is True
        assert any("dataset vinculado ha sido modificado" in r for r in reasons)

    def test_reader_adapter_valid_delivery_and_rejections(self, tmp_path):
        h = _create_harness(tmp_path)
        proj = _seed_project(h)
        doc = _seed_document(h, proj.id)
        dataset = _seed_dataset(h, proj.id)
        vars_, dims, inds, items, rules = _sample_structure()
        _seed_methodology_review(h, proj.id, doc.id, vars_[0].variable_id)

        # 1. Draft rechaza lectura autorizada
        draft = h["service"].create_draft(proj.id, vars_, dims, inds, items, rules)
        with pytest.raises(InstrumentNotConfirmedError):
            h["reader"].get_confirmed_context(str(proj.id), str(draft.instrument_id))

        # 2. Vincular y confirmar instrumento y mapeo
        linked = h["service"].link_methodology(proj.id, draft.instrument_id, 0, doc.id)
        mapping_cols = [
            ItemColumnMapping(item_id=items[0].item_id, column_name="p1"),
            ItemColumnMapping(item_id=items[1].item_id, column_name="p2"),
        ]
        mapped = h["service"].set_mapping(
            proj.id, draft.instrument_id, linked.version, dataset.id, mapping_cols
        )
        mapped_conf = h["service"].confirm_mapping(
            proj.id, draft.instrument_id, mapped.version, "rev"
        )
        rules_conf = h["service"].confirm_scoring_rules(
            proj.id, draft.instrument_id, mapped_conf.version
        )
        confirmed = h["service"].confirm_instrument(
            proj.id, draft.instrument_id, rules_conf.version, "rev"
        )

        # Lectura exitosa por el puerto autorizado
        context = h["reader"].get_confirmed_context(str(proj.id), str(confirmed.instrument_id))
        assert context.status == "reviewed"
        assert context.confirmation.state == "confirmed"
        assert context.dataset_mapping.status == "confirmed"

    def test_reader_rejects_stale_instrument(self, tmp_path):
        h = _create_harness(tmp_path)
        proj = _seed_project(h)
        doc = _seed_document(h, proj.id)
        vars_, dims, inds, items, rules = _sample_structure()
        review = _seed_methodology_review(h, proj.id, doc.id, vars_[0].variable_id)

        inst = h["service"].create_draft(proj.id, vars_, dims, inds, items, rules)
        linked = h["service"].link_methodology(proj.id, inst.instrument_id, 0, doc.id)
        rules_conf = h["service"].confirm_scoring_rules(proj.id, inst.instrument_id, linked.version)
        confirmed = h["service"].confirm_instrument(
            proj.id, inst.instrument_id, rules_conf.version, "rev"
        )

        # Modificar metodología
        updated_review = review.model_copy(update={"version": 3})
        h["methodology"].save_review(updated_review, expected_version=1)

        # Reader debe rechazar por stale
        with pytest.raises(InstrumentStaleError) as exc:
            h["reader"].get_confirmed_context(str(proj.id), str(confirmed.instrument_id))
        assert "está desactualizado" in str(exc.value)

    def test_reject_cross_project_access(self, tmp_path):
        h = _create_harness(tmp_path)
        proj1 = _seed_project(h)
        proj2 = h["projects"].create(
            ProjectDraft(
                title="Proyecto 2",
                university="U2",
                program="P2",
                degree="master",
            )
        )
        vars_, dims, inds, items, rules = _sample_structure()
        inst = h["service"].create_draft(proj1.id, vars_, dims, inds, items, rules)

        with pytest.raises(InstrumentNotFound):
            h["service"].get(proj2.id, inst.instrument_id)

        with pytest.raises(InstrumentNotFound):
            h["reader"].get_confirmed_context(str(proj2.id), str(inst.instrument_id))

    def test_version_history_preservation(self, tmp_path):
        h = _create_harness(tmp_path)
        proj = _seed_project(h)
        doc = _seed_document(h, proj.id)
        vars_, dims, inds, items, rules = _sample_structure()
        _seed_methodology_review(h, proj.id, doc.id, vars_[0].variable_id)

        # v0: draft inicial
        v0 = h["service"].create_draft(proj.id, vars_, dims, inds, items, rules)
        # v1: vincular metodología
        v1 = h["service"].link_methodology(proj.id, v0.instrument_id, 0, doc.id)
        # v2: confirmar reglas de puntuación
        v2 = h["service"].confirm_scoring_rules(proj.id, v0.instrument_id, v1.version)
        # v3: confirmación de instrumento
        h["service"].confirm_instrument(proj.id, v0.instrument_id, v2.version, "rev")

        history = h["service"].get_history(proj.id, v0.instrument_id)
        assert len(history) == 4
        assert [item.version for item in history] == [0, 1, 2, 3]
        assert history[0].status == "draft"
        assert history[3].status == "reviewed"

        # Recuperar snapshot histórico específico v0
        historic_v0 = h["service"].get(proj.id, v0.instrument_id, version=0)
        assert historic_v0.version == 0
        assert historic_v0.status == "draft"

    def test_original_dataset_never_modified(self, tmp_path):
        h = _create_harness(tmp_path)
        proj = _seed_project(h)
        original_bytes = b"p1,p2,extra\n10,20,test\n"
        dataset = _seed_dataset(h, proj.id, original_bytes)
        vars_, dims, inds, items, rules = _sample_structure()
        inst = h["service"].create_draft(proj.id, vars_, dims, inds, items, rules)

        mapping_cols = [
            ItemColumnMapping(item_id=items[0].item_id, column_name="p1"),
            ItemColumnMapping(item_id=items[1].item_id, column_name="p2"),
        ]
        h["service"].set_mapping(proj.id, inst.instrument_id, 0, dataset.id, mapping_cols)

        # Los bytes y metadatos permanecen 100% inalterados
        persisted_bytes = h["datasets"].read(proj.id, dataset.id)
        assert persisted_bytes == original_bytes
        persisted_ds = h["datasets"].get(proj.id, dataset.id)
        assert persisted_ds.columns == ["p1", "p2", "extra"]


class TestSQLiteIntegrityAndCascades:
    """Rigorous verification of SQLite foreign keys, cascades, and consistency."""

    def test_cannot_create_instrument_for_nonexistent_project(self, tmp_path):
        h = _create_harness(tmp_path)
        fake_proj_id = uuid4()
        vars_, dims, inds, items, rules = _sample_structure()

        # Validación a nivel de servicio de aplicación
        with pytest.raises(InstrumentNotFound):
            h["service"].create_draft(fake_proj_id, vars_, dims, inds, items, rules)

        # Validación a nivel de motor SQLite (FK constraint a research_projects)
        from app.modules.research.instrument.contracts import InstrumentContext
        from app.modules.research.instrument.models import InstrumentConfirmation

        now = datetime.now(UTC)
        dummy_inst = InstrumentContext(
            instrument_id=uuid4(),
            project_id=fake_proj_id,
            version=0,
            status="draft",
            created_at=now,
            updated_at=now,
            confirmation=InstrumentConfirmation(state="pending"),
            variables=vars_,
            dimensions=dims,
            indicators=inds,
            items=items,
            scoring_rules=rules,
        )
        with pytest.raises(InstrumentValidationError) as exc_info:
            h["instrument_repo"].create(dummy_inst)
        assert "no existe en la base de datos" in str(exc_info.value)

    def test_foreign_key_references_real_table(self, tmp_path):
        h = _create_harness(tmp_path)
        with closing(h["instrument_repo"]._connect()) as conn:
            fks = conn.execute("PRAGMA foreign_key_list(research_instruments)").fetchall()
            # columns: (id, seq, table, from, to, on_update, on_delete, match)
            assert len(fks) >= 1
            fk_target_table = fks[0][2]
            fk_from_col = fks[0][3]
            fk_to_col = fks[0][4]
            fk_on_delete = fks[0][6]

            assert fk_target_table == "research_projects"
            assert fk_from_col == "project_id"
            assert fk_to_col == "id"
            assert fk_on_delete.upper() == "CASCADE"

    def test_pragma_foreign_key_check_passes(self, tmp_path):
        h = _create_harness(tmp_path)
        proj = _seed_project(h)
        vars_, dims, inds, items, rules = _sample_structure()
        h["service"].create_draft(proj.id, vars_, dims, inds, items, rules)

        with closing(h["instrument_repo"]._connect()) as conn:
            fk_violations = conn.execute("PRAGMA foreign_key_check").fetchall()
            assert fk_violations == []

    def test_cascade_deletion_when_project_is_deleted(self, tmp_path):
        h = _create_harness(tmp_path)
        proj = _seed_project(h)
        doc = _seed_document(h, proj.id)
        vars_, dims, inds, items, rules = _sample_structure()
        _seed_methodology_review(h, proj.id, doc.id, vars_[0].variable_id)

        v0 = h["service"].create_draft(proj.id, vars_, dims, inds, items, rules)
        v1 = h["service"].link_methodology(proj.id, v0.instrument_id, 0, doc.id)
        v2 = h["service"].confirm_scoring_rules(proj.id, v0.instrument_id, v1.version)
        h["service"].confirm_instrument(proj.id, v0.instrument_id, v2.version, "rev")

        # Verificar que existen 4 registros históricos en BD
        with closing(h["instrument_repo"]._connect()) as conn:
            count = conn.execute(
                "SELECT count(*) FROM research_instruments WHERE project_id = ?",
                (str(proj.id),),
            ).fetchone()[0]
            assert count == 4

        # Eliminar el proyecto usando el ProjectService
        h["projects"].delete(proj.id)

        # Verificar que el instrumento ya no es accesible por servicio
        with pytest.raises(InstrumentNotFound):
            h["service"].get(proj.id, v0.instrument_id)

        # Verificar que se eliminaron todas las versiones en la base de datos
        with closing(h["instrument_repo"]._connect()) as conn:
            remaining = conn.execute(
                "SELECT count(*) FROM research_instruments WHERE project_id = ?",
                (str(proj.id),),
            ).fetchone()[0]
            assert remaining == 0
            fk_violations = conn.execute("PRAGMA foreign_key_check").fetchall()
            assert fk_violations == []

    def test_version_history_preserved_while_project_exists(self, tmp_path):
        h = _create_harness(tmp_path)
        proj = _seed_project(h)
        doc = _seed_document(h, proj.id)
        vars_, dims, inds, items, rules = _sample_structure()
        _seed_methodology_review(h, proj.id, doc.id, vars_[0].variable_id)

        v0 = h["service"].create_draft(proj.id, vars_, dims, inds, items, rules)
        v1 = h["service"].link_methodology(proj.id, v0.instrument_id, 0, doc.id)
        v2 = h["service"].confirm_scoring_rules(proj.id, v0.instrument_id, v1.version)
        h["service"].confirm_instrument(proj.id, v0.instrument_id, v2.version, "rev")

        history = h["service"].get_history(proj.id, v0.instrument_id)
        assert len(history) == 4
        assert [h_item.version for h_item in history] == [0, 1, 2, 3]

        with closing(h["instrument_repo"]._connect()) as conn:
            rows = conn.execute(
                "SELECT version, is_current FROM research_instruments "
                "WHERE project_id = ? ORDER BY version",
                (str(proj.id),),
            ).fetchall()
            assert rows == [(0, 0), (1, 0), (2, 0), (3, 1)]

    def test_project_deletion_does_not_affect_other_projects(self, tmp_path):
        h = _create_harness(tmp_path)
        proj1 = _seed_project(h)
        proj2 = h["projects"].create(
            ProjectDraft(
                title="Segundo Proyecto de Investigacion",
                university="Universidad Catolica",
                faculty="Ciencias Sociales",
                program="Antropologia",
                degree="master",
            )
        )
        vars_, dims, inds, items, rules = _sample_structure()
        inst1 = h["service"].create_draft(proj1.id, vars_, dims, inds, items, rules)
        inst2 = h["service"].create_draft(proj2.id, vars_, dims, inds, items, rules)

        # Eliminar proj1
        h["projects"].delete(proj1.id)

        # proj1 ya no existe
        with pytest.raises(InstrumentNotFound):
            h["service"].get(proj1.id, inst1.instrument_id)

        # proj2 permanece intacto
        loaded2 = h["service"].get(proj2.id, inst2.instrument_id)
        assert loaded2.instrument_id == inst2.instrument_id
        assert loaded2.project_id == proj2.id

    def test_reopen_sqlite_connection_consistency(self, tmp_path):
        h = _create_harness(tmp_path)
        proj = _seed_project(h)
        vars_, dims, inds, items, rules = _sample_structure()
        inst = h["service"].create_draft(proj.id, vars_, dims, inds, items, rules)

        # Cerrar y abrir nueva instancia apuntando al mismo archivo SQLite
        new_repo = SQLiteInstrumentRepository(h["db_path"])
        with closing(new_repo._connect()) as conn:
            fk_pragma = conn.execute("PRAGMA foreign_keys").fetchone()[0]
            assert fk_pragma == 1
            fk_violations = conn.execute("PRAGMA foreign_key_check").fetchall()
            assert fk_violations == []

        loaded = new_repo.get(proj.id, inst.instrument_id)
        assert loaded is not None
        assert loaded.instrument_id == inst.instrument_id

    def test_confirm_instrument_rejects_unconfirmed_scoring_rules(self, tmp_path):
        """Demuestra que confirm_instrument no auto-confirma reglas silenciosamente."""
        h = _create_harness(tmp_path)
        proj = _seed_project(h)
        doc = _seed_document(h, proj.id)
        vars_, dims, inds, items, rules = _sample_structure()
        assert rules[0].confirmed is False
        _seed_methodology_review(h, proj.id, doc.id, vars_[0].variable_id)

        inst = h["service"].create_draft(proj.id, vars_, dims, inds, items, rules)
        linked = h["service"].link_methodology(proj.id, inst.instrument_id, 0, doc.id)

        # Intento de confirmar instrumento sin confirmar las reglas explícitamente
        with pytest.raises(InstrumentValidationError) as exc:
            h["service"].confirm_instrument(proj.id, inst.instrument_id, linked.version, "rev")
        assert "pendientes de confirmación explícita" in str(exc.value)

        # Confirmación explícita de la regla
        rules_conf = h["service"].confirm_scoring_rules(
            proj.id, inst.instrument_id, linked.version, [rules[0].scoring_rule_id]
        )
        assert rules_conf.scoring_rules[0].confirmed is True

        # Ahora sí se puede confirmar el instrumento
        confirmed = h["service"].confirm_instrument(
            proj.id, inst.instrument_id, rules_conf.version, "rev"
        )
        assert confirmed.status == "reviewed"

    def test_link_methodology_rejects_unlinked_or_invalid_variables(self, tmp_path):
        """Demuestra que vincular metodología exige correspondencia metodológica en variables."""
        h = _create_harness(tmp_path)
        proj = _seed_project(h)
        doc = _seed_document(h, proj.id)
        vars_, dims, inds, items, rules = _sample_structure()
        review = _seed_methodology_review(h, proj.id, doc.id, vars_[0].variable_id)

        # 1. Variable sin methodology_variable_id
        unlinked_var = vars_[0].model_copy(update={"methodology_variable_id": None})
        inst1 = h["service"].create_draft(proj.id, [unlinked_var], dims, inds, items, rules)
        with pytest.raises(InstrumentValidationError) as exc1:
            h["service"].link_methodology(proj.id, inst1.instrument_id, 0, doc.id)
        assert "no tiene una correspondencia metodológica asignada" in str(exc1.value)

        # Vinculación explícita mediante variable_links
        valid_linked = h["service"].link_methodology(
            proj.id,
            inst1.instrument_id,
            0,
            doc.id,
            variable_links={unlinked_var.variable_id: review.content.variables[0].id},
        )
        assert valid_linked.variables[0].methodology_variable_id == review.content.variables[0].id

        # 2. Variable con ID inexistente en la metodología confirmada
        bad_var = vars_[0].model_copy(update={"methodology_variable_id": uuid4()})
        inst2 = h["service"].create_draft(proj.id, [bad_var], dims, inds, items, rules)
        with pytest.raises(InstrumentValidationError) as exc2:
            h["service"].link_methodology(proj.id, inst2.instrument_id, 0, doc.id)
        assert "inexistente en la metodología confirmada" in str(exc2.value)

    def test_update_draft_invalidates_confirmed_dataset_mapping(self, tmp_path):
        """Demuestra que actualizar el borrador invalida el mapeo confirmado previo."""
        h = _create_harness(tmp_path)
        proj = _seed_project(h)
        doc = _seed_document(h, proj.id)
        dataset = _seed_dataset(h, proj.id)
        vars_, dims, inds, items, rules = _sample_structure()
        _seed_methodology_review(h, proj.id, doc.id, vars_[0].variable_id)

        inst = h["service"].create_draft(proj.id, vars_, dims, inds, items, rules)
        linked = h["service"].link_methodology(proj.id, inst.instrument_id, 0, doc.id)
        mapping_cols = [
            ItemColumnMapping(item_id=items[0].item_id, column_name="p1"),
            ItemColumnMapping(item_id=items[1].item_id, column_name="p2"),
        ]
        mapped = h["service"].set_mapping(
            proj.id, inst.instrument_id, linked.version, dataset.id, mapping_cols
        )
        conf_map = h["service"].confirm_mapping(
            proj.id, inst.instrument_id, mapped.version, "rev_data"
        )
        assert conf_map.dataset_mapping.status == "confirmed"
        assert conf_map.dataset_mapping.confirmation.state == "confirmed"
        assert conf_map.version == 3

        # Actualizar el borrador modificando un ítem
        new_items = list(items)
        new_items[0] = items[0].model_copy(update={"text": "Texto sustancialmente modificado"})
        updated = h["service"].update_draft(
            proj.id,
            inst.instrument_id,
            expected_version=3,
            items=new_items,
        )
        assert updated.version == 4
        # El mapeo no puede permanecer confirmed; se resetea a draft/pending
        assert updated.dataset_mapping is not None
        assert updated.dataset_mapping.status == "draft"
        assert updated.dataset_mapping.confirmation.state == "pending"
        assert updated.dataset_mapping.instrument_version == 4

        # El snapshot histórico v3 en la base de datos conserva el mapeo confirmed intacto
        historic_v3 = h["service"].get(proj.id, inst.instrument_id, version=3)
        assert historic_v3.version == 3
        assert historic_v3.dataset_mapping.status == "confirmed"
        assert historic_v3.dataset_mapping.confirmation.state == "confirmed"

    def test_mark_stale_explicit_transactional_versioning(self, tmp_path):
        """Demuestra la materialización transaccional explícita de stale sin efectos en lectura."""
        h = _create_harness(tmp_path)
        proj = _seed_project(h)
        doc = _seed_document(h, proj.id)
        vars_, dims, inds, items, rules = _sample_structure()
        review = _seed_methodology_review(h, proj.id, doc.id, vars_[0].variable_id)

        inst = h["service"].create_draft(proj.id, vars_, dims, inds, items, rules)
        linked = h["service"].link_methodology(proj.id, inst.instrument_id, 0, doc.id)
        rules_conf = h["service"].confirm_scoring_rules(proj.id, inst.instrument_id, linked.version)
        confirmed = h["service"].confirm_instrument(
            proj.id, inst.instrument_id, rules_conf.version, "rev"
        )

        # Modificar metodología
        updated_review = review.model_copy(
            update={
                "content": ReviewContent(title=ReviewFinding(value="Nuevo Titulo", kind="manual"))
            }
        )
        h["methodology"].save_review(updated_review, expected_version=1)

        # Lectura normal no escribe en base de datos
        history_before = h["service"].get_history(proj.id, inst.instrument_id)
        with pytest.raises(InstrumentStaleError):
            h["reader"].get_confirmed_context(str(proj.id), str(inst.instrument_id))

        history_after_read = h["service"].get_history(proj.id, inst.instrument_id)
        assert len(history_after_read) == len(history_before)

        # Materialización transaccional explícita mediante mark_stale
        stale_inst = h["service"].mark_stale(proj.id, inst.instrument_id, confirmed.version)
        assert stale_inst.version == confirmed.version + 1
        assert stale_inst.status == "stale"

        # Historial preserva el snapshot confirmed previo
        history_final = h["service"].get_history(proj.id, inst.instrument_id)
        assert len(history_final) == len(history_before) + 1
        assert history_final[-2].status == "reviewed"
        assert history_final[-1].status == "stale"

    def test_public_fixture_examples_lifecycle_coherence(self, tmp_path):
        """Tarea 4: Demuestra que ejemplos publicados reflejan estados de InstrumentService."""
        from pathlib import Path

        from app.shared.instrument_contracts import InstrumentContext

        root = Path(__file__).resolve().parents[3]
        ex1_path = (
            root / "docs" / "contracts" / "examples" / "instrument_confirmed_with_mapping.json"
        )
        ex2_path = (
            root / "docs" / "contracts" / "examples" / "instrument_reviewed_without_mapping.json"
        )

        inst1 = InstrumentContext.model_validate_json(ex1_path.read_text(encoding="utf-8"))
        inst2 = InstrumentContext.model_validate_json(ex2_path.read_text(encoding="utf-8"))

        # Verificación de ciclo de vida real:
        # 1. Ambos son reviewed y tienen versiones exactas según el flujo
        assert inst1.version == 5
        assert inst1.status == "reviewed"
        assert inst2.version == 3
        assert inst2.status == "reviewed"

        # 2. Ambos tienen correspondencia metodológica no nula (requerida por confirm_instrument)
        assert inst1.variables[0].methodology_variable_id is not None
        assert inst2.variables[0].methodology_variable_id is not None

        # 3. Marcas temporales coherentes: updated_at coincide con confirmed_at
        assert inst1.updated_at == inst1.confirmation.confirmed_at
        assert inst2.updated_at == inst2.confirmation.confirmed_at

        # 4. El fixture 1 tiene dataset mapping confirmado al 100% y versión sincronizada
        assert inst1.dataset_mapping is not None
        assert inst1.dataset_mapping.status == "confirmed"
        assert inst1.dataset_mapping.instrument_version == 5
        assert len(inst1.dataset_mapping.item_columns) == len(inst1.items)

        # 5. El fixture 2 representa un instrumento revisado SIN dataset (no apto para datos aún)
        assert inst2.dataset_mapping is None

        # 6. Hashes reales calculados a partir de contenido sintético (no artificiales ni repetidos)
        assert inst1.provenance.source_document_hash != "a" * 64
        assert inst1.provenance.methodology_review_hash != "b" * 64
        assert inst1.dataset_mapping.dataset_hash != "c" * 64

    def test_synthetic_fixture_reproducibility_full_lifecycle(self, tmp_path):
        """Demuestra el ciclo de vida completo de 11 pasos para generar contextos reproducibles."""
        h = _create_harness(tmp_path)
        proj = _seed_project(h)

        # 1-3. Documento y revisión metodológica confirmada
        doc_content = b"%PDF-1.4\nCuestionario Clima Laboral y Autoeficacia 2026\n%%EOF"
        doc = _seed_document(h, proj.id, content=doc_content)
        meth_var_id = uuid4()
        review = _seed_methodology_review(h, proj.id, doc.id, meth_var_id)
        assert review.review_status == "reviewed"

        # Dataset sintético
        ds_data = b"p1_comunicacion_directa,p2_info_contradictoria\n1,5\n2,4\n3,3\n"
        ds = h["datasets"].add(proj.id, "clima_dataset.csv", ds_data)

        # 4. Crear borrador de instrumento (v0)
        var_id = uuid4()
        dim_id = uuid4()
        ind_id = uuid4()
        item1_id = uuid4()
        item2_id = uuid4()
        rule_id = uuid4()

        opts = standard_likert_options()
        items = [
            InstrumentItem(
                item_id=item1_id,
                variable_id=var_id,
                dimension_id=dim_id,
                indicator_id=ind_id,
                text="La comunicación de la dirección es oportuna y clara.",
                response_type="single_choice",
                response_options=opts,
                valid_min=1.0,
                valid_max=5.0,
                reverse_scored=False,
            ),
            InstrumentItem(
                item_id=item2_id,
                variable_id=var_id,
                dimension_id=dim_id,
                indicator_id=ind_id,
                text="Frecuentemente recibo información contradictoria de mis superiores.",
                response_type="single_choice",
                response_options=opts,
                valid_min=1.0,
                valid_max=5.0,
                reverse_scored=True,
                reverse_rule="min_plus_max_minus_value",
            ),
        ]
        rules = [
            ScoringRule(
                scoring_rule_id=rule_id,
                scope="dimension",
                dimension_id=dim_id,
                item_ids=[item1_id, item2_id],
                aggregation="sum",
                missing_policy="all_required",
                confirmed=False,
            )
        ]

        v0 = h["service"].create_draft(
            proj.id,
            variables=[
                InstrumentVariable(variable_id=var_id, name="Clima Laboral", scale="ordinal")
            ],
            dimensions=[
                InstrumentDimension(
                    dimension_id=dim_id, variable_id=var_id, name="Comunicación Interna"
                )
            ],
            indicators=[
                InstrumentIndicator(
                    indicator_id=ind_id, dimension_id=dim_id, name="Claridad de Información"
                )
            ],
            items=items,
            scoring_rules=rules,
        )
        assert v0.version == 0
        assert v0.status == "draft"

        # 5. Vincular variables metodológicas (v1)
        v1 = h["service"].link_methodology(
            proj.id, v0.instrument_id, 0, doc.id, {var_id: meth_var_id}
        )
        assert v1.version == 1
        assert v1.provenance is not None
        assert v1.variables[0].methodology_variable_id == meth_var_id

        # 6. Confirmar reglas de puntuación (v2)
        v2 = h["service"].confirm_scoring_rules(proj.id, v0.instrument_id, 1)
        assert v2.version == 2
        assert all(r.confirmed for r in v2.scoring_rules)

        # 7. Configurar mapeo (v3) y confirmarlo (v4)
        v3 = h["service"].set_mapping(
            proj.id,
            v0.instrument_id,
            2,
            ds.id,
            [
                ItemColumnMapping(item_id=item1_id, column_name="p1_comunicacion_directa"),
                ItemColumnMapping(item_id=item2_id, column_name="p2_info_contradictoria"),
            ],
        )
        assert v3.version == 3
        assert v3.dataset_mapping.status == "draft"

        v4 = h["service"].confirm_mapping(proj.id, v0.instrument_id, 3, "revisor_metodologico")
        assert v4.version == 4
        assert v4.dataset_mapping.status == "confirmed"

        # 8. Confirmar instrumento (v5)
        v5 = h["service"].confirm_instrument(proj.id, v0.instrument_id, 4, "revisor_metodologico")
        assert v5.version == 5
        assert v5.status == "reviewed"
        assert v5.confirmation.state == "confirmed"
        assert v5.dataset_mapping.instrument_version == 5

        # 9. Obtener contexto mediante el lector autorizado
        ctx = h["reader"].get_confirmed_context(str(proj.id), str(v0.instrument_id))
        assert ctx.version == 5
        assert ctx.status == "reviewed"

        # 10-11. Serializar y verificar que re-valida con el contrato canónico
        serialized = ctx.model_dump_json()
        restored = InstrumentContext.model_validate_json(serialized)
        assert restored.instrument_id == ctx.instrument_id
        assert restored.version == 5

    def test_deterministic_fixture_confirmed_with_mapping_double_generation(self):
        """Requisito 3.1 & 3.2: Genera contexto con mapeo y comprueba igualdad exacta."""
        ctx_a = build_deterministic_confirmed_instrument_with_mapping()
        ctx_b = build_deterministic_confirmed_instrument_with_mapping()

        # Igualdad exacta de modelo y de serialización canónica
        assert ctx_a == ctx_b
        json_a = ctx_a.model_dump_json(indent=2)
        json_b = ctx_b.model_dump_json(indent=2)
        assert json_a == json_b

        # Verificación exhaustiva: versiones, UUIDs, timestamps y hashes reales
        assert ctx_a.version == 5
        assert ctx_a.status == "reviewed"
        assert ctx_a.schema_version == "1.0.0"
        assert ctx_a.instrument_id == deterministic_uuid("instrument:clima")
        assert ctx_a.project_id == deterministic_uuid("project:clima")
        assert ctx_a.created_at == datetime(2026, 11, 1, 10, 0, 0, tzinfo=UTC)
        assert ctx_a.updated_at == datetime(2026, 11, 1, 10, 5, 0, tzinfo=UTC)
        assert ctx_a.confirmation.state == "confirmed"
        assert ctx_a.confirmation.confirmed_at == datetime(2026, 11, 1, 10, 5, 0, tzinfo=UTC)
        assert ctx_a.confirmation.confirmer_ref == "revisor_metodologico"

        # Hashes SHA-256 reales (longitud 64, caracteres hexadecimales, no cadenas repetidas)
        assert len(ctx_a.provenance.source_document_hash) == 64
        assert len(ctx_a.provenance.methodology_review_hash) == 64
        assert len(ctx_a.dataset_mapping.dataset_hash) == 64
        assert ctx_a.provenance.source_document_hash != "a" * 64
        assert ctx_a.provenance.methodology_review_hash != "b" * 64
        assert ctx_a.dataset_mapping.dataset_hash != "c" * 64

        # Mapeo y variables
        assert ctx_a.dataset_mapping.instrument_version == 5
        assert ctx_a.dataset_mapping.status == "confirmed"
        assert ctx_a.dataset_mapping.confirmation.confirmed_at == datetime(
            2026, 11, 1, 10, 4, 0, tzinfo=UTC
        )
        assert len(ctx_a.items) == 2
        assert len(ctx_a.scoring_rules) == 1
        assert ctx_a.scoring_rules[0].confirmed is True

    def test_deterministic_fixture_reviewed_without_mapping_double_generation(self):
        """Requisito 3.3 & 3.4: Genera contexto revisado y comprueba igualdad exacta."""
        ctx_a = build_deterministic_reviewed_instrument_without_mapping()
        ctx_b = build_deterministic_reviewed_instrument_without_mapping()

        assert ctx_a == ctx_b
        json_a = ctx_a.model_dump_json(indent=2)
        json_b = ctx_b.model_dump_json(indent=2)
        assert json_a == json_b

        assert ctx_a.version == 3
        assert ctx_a.status == "reviewed"
        assert ctx_a.schema_version == "1.0.0"
        assert ctx_a.instrument_id == deterministic_uuid("instrument:autoeficacia")
        assert ctx_a.project_id == deterministic_uuid("project:autoeficacia")
        assert ctx_a.created_at == datetime(2026, 11, 1, 10, 0, 0, tzinfo=UTC)
        assert ctx_a.updated_at == datetime(2026, 11, 1, 10, 3, 0, tzinfo=UTC)
        assert ctx_a.confirmation.state == "confirmed"
        assert ctx_a.confirmation.confirmed_at == datetime(2026, 11, 1, 10, 3, 0, tzinfo=UTC)
        assert ctx_a.dataset_mapping is None

        # Hashes SHA-256 reales
        assert len(ctx_a.provenance.source_document_hash) == 64
        assert len(ctx_a.provenance.methodology_review_hash) == 64

    def test_deterministic_fixtures_match_versioned_json_files(self):
        """Requisito 3.5-3.7: Compara contra ejemplos versionados y valida con DTO canónico."""
        from pathlib import Path

        root = Path(__file__).resolve().parents[3]
        ex1_path = (
            root / "docs" / "contracts" / "examples" / "instrument_confirmed_with_mapping.json"
        )
        ex2_path = (
            root / "docs" / "contracts" / "examples" / "instrument_reviewed_without_mapping.json"
        )

        ctx_confirmed = build_deterministic_confirmed_instrument_with_mapping()
        ctx_reviewed = build_deterministic_reviewed_instrument_without_mapping()

        expected_json_confirmed = ctx_confirmed.model_dump_json(indent=2) + "\n"
        expected_json_reviewed = ctx_reviewed.model_dump_json(indent=2) + "\n"

        actual_json_confirmed = ex1_path.read_text(encoding="utf-8")
        actual_json_reviewed = ex2_path.read_text(encoding="utf-8")

        assert actual_json_confirmed == expected_json_confirmed
        assert actual_json_reviewed == expected_json_reviewed

        # Validación mediante DTO canónico público
        dto1 = InstrumentContext.model_validate_json(actual_json_confirmed)
        dto2 = InstrumentContext.model_validate_json(actual_json_reviewed)
        assert dto1 == ctx_confirmed
        assert dto2 == ctx_reviewed

    def test_deterministic_lifecycle_authorized_reader_and_stale_detection(self, tmp_path):
        """Requisito 3.8: Comprueba lectura autorizada y detección de stale sobre flujo real."""
        # 1. Ejecutar ciclo determinista en directorio controlado
        ctx = build_deterministic_confirmed_instrument_with_mapping(storage_dir=tmp_path)
        assert ctx.version == 5
        assert ctx.status == "reviewed"

        # 2. Conectar arnés al directorio persistido y leer con lector autorizado
        h = create_deterministic_harness(tmp_path)
        read_ctx = h["reader"].get_confirmed_context(str(ctx.project_id), str(ctx.instrument_id))
        assert read_ctx == ctx

        # 3. Comprobar ausencia inicial de stale
        is_stale, reasons = h["service"].check_stale(ctx.project_id, ctx.instrument_id)
        assert is_stale is False
        assert len(reasons) == 0

        # 4. Alterar el contenido del dataset vinculado para forzar divergencia de hash
        ds_path = h["dataset_repo"]._path(ctx.dataset_mapping.dataset_id)
        ds_path.write_bytes(b"p1_comunicacion_directa,p2_info_contradictoria\n9,9\n")

        # 5. Comprobar que check_stale detecta la discrepancia
        is_stale_after, reasons_after = h["service"].check_stale(ctx.project_id, ctx.instrument_id)
        assert is_stale_after is True
        assert any("dataset" in r.lower() for r in reasons_after)

        # 6. Comprobar que el lector autorizado rechaza servir el contexto si ha quedado stale
        with pytest.raises(InstrumentStaleError) as exc_info:
            h["reader"].get_confirmed_context(str(ctx.project_id), str(ctx.instrument_id))
        assert "desactualizado" in str(exc_info.value).lower()
