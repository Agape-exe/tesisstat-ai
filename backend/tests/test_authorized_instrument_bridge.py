"""Comprehensive tests for the authorized InstrumentContext & dataset rows composition bridge.

Validates:
- Deterministic end-to-end positive harness (steps 1 to 10).
- Pure Statistics consumption (scoring, reverse item recoding, Cronbach's alpha).
- Data immutability and isolation (no alteration to original storage).
- Scoring rule column filtering (restricting rows strictly to rule items).
- Missing value normalization (CSV empty strings -> None -> all_required missing policy).
- XLSX formula detection (uncalculated formulas rejected).
- Full negative matrix: foreign project, nonexistent instrument, draft status, stale status,
  unconfirmed mapping, stale mapping, version mismatch, deleted dataset, hash mismatch,
  missing column, invalid format, corrupt mapping, and concurrent modifications.
"""

from __future__ import annotations

import io
import json
from datetime import UTC, datetime
from uuid import uuid4

import openpyxl
import pytest

from app.modules.research.datasets.sqlite_repository import SQLiteDatasetRepository
from app.modules.research.datasets.use_cases import DatasetService
from app.modules.research.documents.models import Document
from app.modules.research.documents.sqlite_repository import SQLiteDocumentRepository
from app.modules.research.documents.use_cases import DocumentService
from app.modules.research.instrument.fixtures import (
    deterministic_uuid,
    make_deterministic_clock,
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
from app.modules.research.instrument.reader import ResearchInstrumentContextReader
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
from app.modules.statistics.scoring_context import (
    calculate_context_cronbach,
    calculate_context_scores,
)
from app.orchestration.research_statistics import (
    AuthorizedInstrumentData,
    InstrumentStatisticsBridge,
    ResearchInputError,
    ResearchStatisticsBridge,
)
from app.shared.ports import InstrumentContextReader


def _setup_test_env(tmp_path):
    db_path = tmp_path / "research_test.db"
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

    clock = make_deterministic_clock(
        start=datetime(2026, 11, 1, 10, 0, 0, tzinfo=UTC), step_seconds=60
    )

    instruments = InstrumentService(
        repository=instrument_repo,
        projects=projects,
        documents=documents,
        methodology=methodology_repo,
        datasets=datasets,
        clock=clock,
    )
    reader = ResearchInstrumentContextReader(instruments)
    instrument_bridge = InstrumentStatisticsBridge(
        projects=projects,
        datasets=datasets,
        instruments=instruments,
        instrument_reader=reader,
    )
    orchestration_bridge = ResearchStatisticsBridge(
        projects=projects,
        packages=None,
        datasets=datasets,
        instruments=instruments,
        instrument_reader=reader,
    )

    return {
        "db_path": db_path,
        "storage_path": storage_path,
        "projects": projects,
        "documents": documents,
        "datasets": datasets,
        "methodology": methodology_repo,
        "instruments": instruments,
        "reader": reader,
        "instrument_bridge": instrument_bridge,
        "bridge": orchestration_bridge,
        "clock": clock,
    }


def _seed_complete_valid_setup(env, extra_columns=True):
    """Seed a reviewed, confirmed instrument with confirmed methodology and dataset mapping."""
    projects = env["projects"]
    documents = env["documents"]
    methodology = env["methodology"]
    datasets = env["datasets"]
    instruments = env["instruments"]

    # 1. Project
    project = projects.create(
        ProjectDraft(
            title="Investigación de Clima y Desempeño",
            university="UNMSM",
            program="Psicología",
            degree="bachelor",
        )
    )
    project_id = project.id

    # 2. Document & Methodology
    doc_content = b"%PDF-1.4\nCuestionario Clima Laboral 2026\n%%EOF"
    doc = Document(
        id=uuid4(),
        project_id=project_id,
        name="instrumento.pdf",
        format="pdf",
        size=len(doc_content),
        uploaded_at=datetime.now(UTC),
    )
    documents.repository.add(doc, doc_content)

    meth_var_id = uuid4()
    review = MethodologyReview(
        project_id=project_id,
        document_id=doc.id,
        origin="manual",
        content=ReviewContent(
            title=ReviewFinding(value="Clima", kind="manual"),
            variables=[
                ReviewVariable(
                    id=meth_var_id,
                    name=ReviewFinding(value="Clima Laboral", kind="manual"),
                )
            ],
        ),
        pending_fields=[],
        review_status="reviewed",
        version=1,
        reviewed_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    methodology.save_review(review, expected_version=None)

    # 3. Synthetic CSV Dataset
    # 5 rows with direct and reverse Likert responses:
    # Row 1: p1=1, p2=5 -> reversed p2=1 -> sum=2
    # Row 2: p1=2, p2=4 -> reversed p2=2 -> sum=4
    # Row 3: p1=3, p2=3 -> reversed p2=3 -> sum=6
    # Row 4: p1=4, p2=2 -> reversed p2=4 -> sum=8
    # Row 5: p1=5, p2=1 -> reversed p2=5 -> sum=10
    if extra_columns:
        csv_bytes = (
            b"p1_comunicacion_directa,p2_info_contradictoria,unmapped_column\n"
            b"1,5,extra1\n"
            b"2,4,extra2\n"
            b"3,3,extra3\n"
            b"4,2,extra4\n"
            b"5,1,extra5\n"
        )
    else:
        csv_bytes = (
            b"p1_comunicacion_directa,p2_info_contradictoria\n"
            b"1,5\n"
            b"2,4\n"
            b"3,3\n"
            b"4,2\n"
            b"5,1\n"
        )
    dataset = datasets.add(project_id, "clima_respuestas.csv", csv_bytes)

    # 4. Instrument Draft
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
            text="La comunicación es clara.",
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
            text="Recibo información contradictoria.",
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

    inst = instruments.create_draft(
        project_id,
        variables=[InstrumentVariable(variable_id=var_id, name="Clima Laboral", scale="ordinal")],
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
    inst_id = inst.instrument_id

    # 5. Link methodology
    instruments.link_methodology(
        project_id,
        inst_id,
        expected_version=0,
        document_id=doc.id,
        variable_links={var_id: meth_var_id},
    )

    # 6. Confirm scoring rules
    instruments.confirm_scoring_rules(project_id, inst_id, expected_version=1)

    # 7. Set and confirm dataset mapping
    instruments.set_mapping(
        project_id,
        inst_id,
        expected_version=2,
        dataset_id=dataset.id,
        item_columns=[
            ItemColumnMapping(item_id=item1_id, column_name="p1_comunicacion_directa"),
            ItemColumnMapping(item_id=item2_id, column_name="p2_info_contradictoria"),
        ],
    )
    instruments.confirm_mapping(
        project_id,
        inst_id,
        expected_version=3,
        confirmer_ref="revisor_metodologico",
    )

    # 8. Confirm instrument
    confirmed_inst = instruments.confirm_instrument(
        project_id,
        inst_id,
        expected_version=4,
        confirmer_ref="revisor_metodologico",
    )

    return {
        "project_id": project_id,
        "instrument_id": inst_id,
        "dataset_id": dataset.id,
        "document_id": doc.id,
        "rule_id": rule_id,
        "item1_id": item1_id,
        "item2_id": item2_id,
        "csv_bytes": csv_bytes,
        "confirmed_context": confirmed_inst,
    }


# =============================================================================
# DETERMINISTIC HARNESS & POSITIVE TESTS (Section 7)
# =============================================================================


def test_deterministic_harness_end_to_end(tmp_path):
    """Executes the full 10-step synthetic test specified in Section 7."""
    env = _setup_test_env(tmp_path)
    seeded = _seed_complete_valid_setup(env, extra_columns=True)

    project_id = seeded["project_id"]
    instrument_id = seeded["instrument_id"]
    dataset_id = seeded["dataset_id"]
    rule_id = seeded["rule_id"]
    original_bytes = seeded["csv_bytes"]

    # Step 6: Recupere el contexto por el puerto público real
    reader: InstrumentContextReader = env["reader"]
    public_context = reader.get_confirmed_context(str(project_id), str(instrument_id))
    assert public_context.status == "reviewed"
    assert public_context.confirmation.state == "confirmed"
    assert public_context.dataset_mapping is not None
    assert public_context.dataset_mapping.status == "confirmed"

    # Step 7: Lea las filas autorizadas
    bridge = env["bridge"]
    auth_data: AuthorizedInstrumentData = bridge.get_authorized_instrument_data(
        project_id, instrument_id
    )

    # Verifica aislamiento: columnas no mapeadas (unmapped_column) NO deben ser entregadas
    assert auth_data.column_names == ("p1_comunicacion_directa", "p2_info_contradictoria")
    assert len(auth_data.rows) == 5
    for row in auth_data.rows:
        assert set(row.keys()) == {"p1_comunicacion_directa", "p2_info_contradictoria"}
        assert "unmapped_column" not in row

    # Comprueba que el objeto admite desempaquetado en tupla (context, rows)
    ctx, rows = auth_data
    assert ctx == public_context
    assert rows == auth_data.rows

    # Step 8: Entregue contexto y filas al consumidor puro de Statistics
    scores = calculate_context_scores(auth_data.context, str(rule_id), auth_data.rows)
    cronbach = calculate_context_cronbach(auth_data.context, str(rule_id), auth_data.rows)

    # Step 9: Compruebe una puntuación conocida, incluyendo inversión
    # Puntuaciones teóricas con inversión min_plus_max_minus_value (1+5-x):
    # p1=1, p2=5 -> 1 + 1 = 2.0
    # p1=2, p2=4 -> 2 + 2 = 4.0
    # p1=3, p2=3 -> 3 + 3 = 6.0
    # p1=4, p2=2 -> 4 + 4 = 8.0
    # p1=5, p2=1 -> 5 + 5 = 10.0
    assert scores.values == (2.0, 4.0, 6.0, 8.0, 10.0)
    assert scores.valid_rows == 5
    assert scores.missing_rows == 0

    # Cronbach's alpha con ítems recodificados idénticos [1,1], [2,2], [3,3], [4,4], [5,5]
    assert cronbach.result.metrics["alpha"] == 1.0
    assert cronbach.valid_rows == 5
    assert cronbach.excluded_rows == 0

    # Step 10: Compruebe que no se hayan alterado los datos originales
    stored_bytes = env["datasets"].read(project_id, dataset_id)
    assert stored_bytes == original_bytes
    stored_meta = env["datasets"].get(project_id, dataset_id)
    assert stored_meta.size == len(original_bytes)
    assert stored_meta.columns == [
        "p1_comunicacion_directa",
        "p2_info_contradictoria",
        "unmapped_column",
    ]


def test_scoring_rule_filter_selects_only_required_columns(tmp_path):
    """Passing scoring_rule_id limits rows strictly to columns mapped to that rule's items."""
    env = _setup_test_env(tmp_path)
    seeded = _seed_complete_valid_setup(env)

    project_id = seeded["project_id"]
    instrument_id = seeded["instrument_id"]
    item1_id = seeded["item1_id"]
    instruments = env["instruments"]

    # Agregar una regla adicional específica para el ítem 1
    rule_item1_id = deterministic_uuid("rule:item1_only")
    current = instruments.get(project_id, instrument_id)
    new_rule = ScoringRule(
        scoring_rule_id=rule_item1_id,
        scope="dimension",
        dimension_id=current.dimensions[0].dimension_id,
        item_ids=[item1_id],
        aggregation="sum",
        missing_policy="all_required",
        confirmed=True,
    )
    new_ver = current.version + 1
    updated_rules = list(current.scoring_rules) + [new_rule]
    instruments.repository.update(
        current.model_copy(
            update={
                "version": new_ver,
                "scoring_rules": updated_rules,
                "dataset_mapping": current.dataset_mapping.model_copy(
                    update={"instrument_version": new_ver}
                ),
            }
        ),
        expected_version=current.version,
    )

    bridge = env["bridge"]
    auth_data = bridge.get_authorized_instrument_data(
        project_id, instrument_id, scoring_rule_id=rule_item1_id
    )

    assert auth_data.column_names == ("p1_comunicacion_directa",)
    for row in auth_data.rows:
        assert list(row.keys()) == ["p1_comunicacion_directa"]
        assert "p2_info_contradictoria" not in row


def test_missing_csv_values_normalized_to_none_and_honors_policy(tmp_path):
    """Empty CSV cells are converted to None, producing missing scores under all_required."""
    env = _setup_test_env(tmp_path)
    seeded = _seed_complete_valid_setup(env, extra_columns=False)

    project_id = seeded["project_id"]
    instrument_id = seeded["instrument_id"]
    rule_id = seeded["rule_id"]

    # Reemplazar con dataset con celdas vacías (faltantes) en la fila 2 y 4
    csv_missing = (
        b"p1_comunicacion_directa,p2_info_contradictoria\n"
        b"1,5\n"
        b"2,\n"  # falta p2
        b"3,3\n"
        b",2\n"  # falta p1
        b"5,1\n"
    )
    # Crear un nuevo dataset con faltantes y remapear
    new_dataset = env["datasets"].add(project_id, "clima_con_faltantes.csv", csv_missing)
    current = env["instruments"].get(project_id, instrument_id)
    instruments = env["instruments"]

    instruments.set_mapping(
        project_id,
        instrument_id,
        expected_version=current.version,
        dataset_id=new_dataset.id,
        item_columns=[
            ItemColumnMapping(item_id=seeded["item1_id"], column_name="p1_comunicacion_directa"),
            ItemColumnMapping(item_id=seeded["item2_id"], column_name="p2_info_contradictoria"),
        ],
    )
    current = instruments.get(project_id, instrument_id)
    instruments.confirm_mapping(
        project_id, instrument_id, expected_version=current.version, confirmer_ref="revisor"
    )
    current = instruments.get(project_id, instrument_id)
    instruments.confirm_instrument(
        project_id, instrument_id, expected_version=current.version, confirmer_ref="revisor"
    )

    auth_data = env["bridge"].get_authorized_instrument_data(project_id, instrument_id)
    assert auth_data.rows[1]["p2_info_contradictoria"] is None
    assert auth_data.rows[3]["p1_comunicacion_directa"] is None

    scores = calculate_context_scores(auth_data.context, str(rule_id), auth_data.rows)
    assert scores.values[0] == 2.0
    assert scores.values[1] is None  # Fila 2 faltante
    assert scores.values[2] == 6.0
    assert scores.values[3] is None  # Fila 4 faltante
    assert scores.values[4] == 10.0
    assert scores.valid_rows == 3
    assert scores.missing_rows == 2


# =============================================================================
# NEGATIVE TESTS (Section 8)
# =============================================================================


def test_foreign_project_or_nonexistent_instrument(tmp_path):
    env = _setup_test_env(tmp_path)
    seeded = _seed_complete_valid_setup(env)
    project_id = seeded["project_id"]
    instrument_id = seeded["instrument_id"]
    bridge = env["bridge"]

    # Proyecto ajeno
    other_project = env["projects"].create(
        ProjectDraft(
            title="Otro Proyecto",
            university="UNI",
            program="Ingenieria",
            degree="master",
        )
    )
    with pytest.raises(ResearchInputError) as exc:
        bridge.get_authorized_instrument_data(other_project.id, instrument_id)
    assert exc.value.code == "instrument_missing"

    # Instrumento inexistente
    with pytest.raises(ResearchInputError) as exc:
        bridge.get_authorized_instrument_data(project_id, uuid4())
    assert exc.value.code == "instrument_missing"

    # Identificadores inválidos
    with pytest.raises(ResearchInputError) as exc:
        bridge.get_authorized_instrument_data("not-a-uuid", instrument_id)
    assert exc.value.code == "invalid_reference"


def test_instrument_in_draft_status_rejected(tmp_path):
    env = _setup_test_env(tmp_path)
    project = env["projects"].create(
        ProjectDraft(
            title="Proyecto Borrador",
            university="UNMSM",
            program="Psicologia",
            degree="bachelor",
        )
    )
    var_id = uuid4()
    dim_id = uuid4()
    ind_id = uuid4()
    item = InstrumentItem(
        item_id=uuid4(),
        variable_id=var_id,
        dimension_id=dim_id,
        indicator_id=ind_id,
        text="Item",
        response_type="single_choice",
        response_options=standard_likert_options(),
        valid_min=1.0,
        valid_max=5.0,
    )
    draft = env["instruments"].create_draft(
        project.id,
        variables=[InstrumentVariable(variable_id=var_id, name="V", scale="ordinal")],
        dimensions=[InstrumentDimension(dimension_id=dim_id, variable_id=var_id, name="D")],
        indicators=[InstrumentIndicator(indicator_id=ind_id, dimension_id=dim_id, name="I")],
        items=[item],
    )

    with pytest.raises(ResearchInputError) as exc:
        env["bridge"].get_authorized_instrument_data(project.id, draft.instrument_id)
    assert exc.value.code == "instrument_not_confirmed"


def test_stale_instrument_rejected(tmp_path):
    env = _setup_test_env(tmp_path)
    seeded = _seed_complete_valid_setup(env)
    project_id = seeded["project_id"]
    instrument_id = seeded["instrument_id"]
    doc_id = seeded["document_id"]

    # Modificar la metodología para provocar obsolescencia
    review = env["methodology"].get_review(project_id, doc_id)
    review_dict = review.model_dump()
    review_dict["version"] = review.version + 1
    review_dict["content"]["title"]["value"] = "Metodología Modificada"
    new_review = MethodologyReview.model_validate(review_dict)
    env["methodology"].save_review(new_review, expected_version=review.version)

    with pytest.raises(ResearchInputError) as exc:
        env["bridge"].get_authorized_instrument_data(project_id, instrument_id)
    assert exc.value.code == "instrument_stale"


def test_pending_dataset_mapping_rejected(tmp_path):
    env = _setup_test_env(tmp_path)
    seeded = _seed_complete_valid_setup(env)
    project_id = seeded["project_id"]
    instrument_id = seeded["instrument_id"]

    # Mapeo en borrador / pendiente de confirmación
    with env["instruments"].repository._connect() as conn:
        row = conn.execute(
            "SELECT payload FROM research_instruments WHERE id = ? AND is_current = 1",
            (str(instrument_id),),
        ).fetchone()
        payload = json.loads(row[0])
        payload["dataset_mapping"]["status"] = "draft"
        payload["dataset_mapping"]["confirmation"] = {"state": "pending"}
        conn.execute(
            "UPDATE research_instruments SET payload = ? WHERE id = ? AND is_current = 1",
            (json.dumps(payload), str(instrument_id)),
        )
        conn.commit()

    with pytest.raises(ResearchInputError) as exc:
        env["bridge"].get_authorized_instrument_data(project_id, instrument_id)
    assert exc.value.code == "mapping_not_confirmed"


def test_stale_dataset_mapping_rejected(tmp_path):
    env = _setup_test_env(tmp_path)
    seeded = _seed_complete_valid_setup(env)
    project_id = seeded["project_id"]
    instrument_id = seeded["instrument_id"]

    # Mapeo con status stale
    with env["instruments"].repository._connect() as conn:
        row = conn.execute(
            "SELECT payload FROM research_instruments WHERE id = ? AND is_current = 1",
            (str(instrument_id),),
        ).fetchone()
        payload = json.loads(row[0])
        payload["dataset_mapping"]["status"] = "stale"
        conn.execute(
            "UPDATE research_instruments SET payload = ? WHERE id = ? AND is_current = 1",
            (json.dumps(payload), str(instrument_id)),
        )
        conn.commit()

    with pytest.raises(ResearchInputError) as exc:
        env["bridge"].get_authorized_instrument_data(project_id, instrument_id)
    assert exc.value.code == "mapping_not_confirmed"


def test_incompatible_version_rejected(tmp_path):
    env = _setup_test_env(tmp_path)
    seeded = _seed_complete_valid_setup(env)
    project_id = seeded["project_id"]
    instrument_id = seeded["instrument_id"]

    # Desalinear versión en la base de datos
    with env["instruments"].repository._connect() as conn:
        row = conn.execute(
            "SELECT payload FROM research_instruments WHERE id = ? AND is_current = 1",
            (str(instrument_id),),
        ).fetchone()
        payload = json.loads(row[0])
        payload["dataset_mapping"]["instrument_version"] = 999
        conn.execute(
            "UPDATE research_instruments SET payload = ? WHERE id = ? AND is_current = 1",
            (json.dumps(payload), str(instrument_id)),
        )
        conn.commit()

    with pytest.raises(ResearchInputError) as exc:
        env["bridge"].get_authorized_instrument_data(project_id, instrument_id)
    assert exc.value.code == "mapping_version_mismatch"


def test_missing_or_corrupted_dataset_rejected(tmp_path):
    env = _setup_test_env(tmp_path)
    seeded = _seed_complete_valid_setup(env)
    project_id = seeded["project_id"]
    instrument_id = seeded["instrument_id"]
    dataset_id = seeded["dataset_id"]

    # Caso 1: Archivo del dataset alterado en disco (hash mismatch)
    storage_file = env["datasets"].repository._path(dataset_id)
    storage_file.write_bytes(b"p1_comunicacion_directa,p2_info_contradictoria\n9,9\n")

    with pytest.raises(ResearchInputError) as exc:
        env["bridge"].get_authorized_instrument_data(project_id, instrument_id)
    assert exc.value.code in ("instrument_stale", "dataset_hash_mismatch", "dataset_incompatible")

    # Caso 2: Dataset eliminado completamente
    env["datasets"].delete(project_id, dataset_id)
    with pytest.raises(ResearchInputError) as exc:
        env["bridge"].get_authorized_instrument_data(project_id, instrument_id)
    assert exc.value.code in ("instrument_stale", "dataset_inaccessible")


def test_mapped_column_missing_in_dataset_rejected(tmp_path):
    env = _setup_test_env(tmp_path)
    seeded = _seed_complete_valid_setup(env)
    project_id = seeded["project_id"]
    instrument_id = seeded["instrument_id"]

    # Inyectar columna mapeada inexistente en la base de datos
    with env["instruments"].repository._connect() as conn:
        row = conn.execute(
            "SELECT payload FROM research_instruments WHERE id = ? AND is_current = 1",
            (str(instrument_id),),
        ).fetchone()
        payload = json.loads(row[0])
        payload["dataset_mapping"]["item_columns"][0]["column_name"] = "columna_fantasma"
        conn.execute(
            "UPDATE research_instruments SET payload = ? WHERE id = ? AND is_current = 1",
            (json.dumps(payload), str(instrument_id)),
        )
        conn.commit()

    with pytest.raises(ResearchInputError) as exc:
        env["bridge"].get_authorized_instrument_data(project_id, instrument_id)
    assert exc.value.code == "mapping_column_missing"


def test_incomplete_item_coverage_in_mapping_rejected(tmp_path):
    env = _setup_test_env(tmp_path)
    seeded = _seed_complete_valid_setup(env)
    project_id = seeded["project_id"]
    instrument_id = seeded["instrument_id"]

    # Mapeo que solo cubre 1 de 2 ítems
    with env["instruments"].repository._connect() as conn:
        row = conn.execute(
            "SELECT payload FROM research_instruments WHERE id = ? AND is_current = 1",
            (str(instrument_id),),
        ).fetchone()
        payload = json.loads(row[0])
        payload["dataset_mapping"]["item_columns"] = [payload["dataset_mapping"]["item_columns"][0]]
        conn.execute(
            "UPDATE research_instruments SET payload = ? WHERE id = ? AND is_current = 1",
            (json.dumps(payload), str(instrument_id)),
        )
        conn.commit()

    with pytest.raises(ResearchInputError) as exc:
        env["bridge"].get_authorized_instrument_data(project_id, instrument_id)
    assert exc.value.code == "mapping_incomplete"


def test_uncalculated_xlsx_formula_detection(tmp_path):
    """Detects uncalculated XLSX formulas and rejects them with dataset_uncalculated_formula."""
    env = _setup_test_env(tmp_path)

    project = env["projects"].create(
        ProjectDraft(
            title="Investigación XLSX",
            university="Universidad Nacional",
            program="Psicologia",
            degree="bachelor",
        )
    )
    project_id = project.id

    # Crear XLSX con fórmula en columna mapeada
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Respuestas"
    ws.append(["p1_comunicacion_directa", "p2_info_contradictoria"])
    ws.append(["4", "=SUM(A2)"])  # Fórmula no calculada en p2
    buf = io.BytesIO()
    wb.save(buf)
    xlsx_bytes = buf.getvalue()

    dataset = env["datasets"].add(project_id, "respuestas.xlsx", xlsx_bytes)

    # Document & Methodology
    doc = Document(
        id=uuid4(),
        project_id=project_id,
        name="test.pdf",
        format="pdf",
        size=10,
        uploaded_at=datetime.now(UTC),
    )
    env["documents"].repository.add(doc, b"%PDF-1.4\nTest\n%%EOF")
    meth_var_id = uuid4()
    review = MethodologyReview(
        project_id=project_id,
        document_id=doc.id,
        origin="manual",
        content=ReviewContent(
            title=ReviewFinding(value="Investigación", kind="manual"),
            variables=[
                ReviewVariable(
                    id=meth_var_id, name=ReviewFinding(value="Variable", kind="manual")
                )
            ],
        ),
        pending_fields=[],
        review_status="reviewed",
        version=1,
        reviewed_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    env["methodology"].save_review(review, expected_version=None)

    # Instrument
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
            text="Item 1",
            response_type="single_choice",
            response_options=opts,
            valid_min=1.0,
            valid_max=5.0,
        ),
        InstrumentItem(
            item_id=item2_id,
            variable_id=var_id,
            dimension_id=dim_id,
            indicator_id=ind_id,
            text="Item 2",
            response_type="single_choice",
            response_options=opts,
            valid_min=1.0,
            valid_max=5.0,
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
    inst = env["instruments"].create_draft(
        project_id,
        variables=[InstrumentVariable(variable_id=var_id, name="V", scale="ordinal")],
        dimensions=[InstrumentDimension(dimension_id=dim_id, variable_id=var_id, name="D")],
        indicators=[InstrumentIndicator(indicator_id=ind_id, dimension_id=dim_id, name="I")],
        items=items,
        scoring_rules=rules,
    )
    inst_id = inst.instrument_id
    env["instruments"].link_methodology(
        project_id,
        inst_id,
        expected_version=0,
        document_id=doc.id,
        variable_links={var_id: meth_var_id},
    )
    env["instruments"].confirm_scoring_rules(project_id, inst_id, expected_version=1)
    env["instruments"].set_mapping(
        project_id,
        inst_id,
        expected_version=2,
        dataset_id=dataset.id,
        item_columns=[
            ItemColumnMapping(item_id=item1_id, column_name="p1_comunicacion_directa"),
            ItemColumnMapping(item_id=item2_id, column_name="p2_info_contradictoria"),
        ],
    )
    env["instruments"].confirm_mapping(
        project_id, inst_id, expected_version=3, confirmer_ref="u"
    )
    env["instruments"].confirm_instrument(
        project_id, inst_id, expected_version=4, confirmer_ref="u"
    )

    with pytest.raises(ResearchInputError) as exc:
        env["bridge"].get_authorized_instrument_data(project_id, inst_id)
    assert exc.value.code == "dataset_uncalculated_formula"


def test_concurrent_instrument_modification_detected(tmp_path):
    """Detects when an instrument context version/updated_at changes during reading."""
    env = _setup_test_env(tmp_path)
    seeded = _seed_complete_valid_setup(env)
    project_id = seeded["project_id"]
    instrument_id = seeded["instrument_id"]

    original_read = env["datasets"].read

    def mutating_read(proj, ds):
        result = original_read(proj, ds)
        # Modificar versión del instrumento directamente en SQLite durante la lectura
        with env["instruments"].repository._connect() as conn:
            conn.execute(
                "UPDATE research_instruments SET version = version + 1 WHERE id = ?",
                (str(instrument_id),),
            )
            conn.commit()
        return result

    env["datasets"].read = mutating_read

    with pytest.raises(ResearchInputError) as exc:
        env["bridge"].get_authorized_instrument_data(project_id, instrument_id)
    assert exc.value.code in ("instrument_concurrent_modification", "instrument_error")


def test_unconfigured_bridge_raises_clear_error(tmp_path):
    """Calling without instrument service raises bridge_unconfigured."""
    env = _setup_test_env(tmp_path)
    unconfigured_bridge = ResearchStatisticsBridge(
        projects=env["projects"],
        packages=None,
        datasets=env["datasets"],
        instruments=None,
    )
    with pytest.raises(ResearchInputError) as exc:
        unconfigured_bridge.get_authorized_instrument_data(uuid4(), uuid4())
    assert exc.value.code == "bridge_unconfigured"
