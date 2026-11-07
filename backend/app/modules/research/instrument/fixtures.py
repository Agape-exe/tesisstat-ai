"""Synthetic fixtures for InstrumentContext v1.0.0 testing and validation."""

import tempfile
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import NAMESPACE_DNS, UUID, uuid4, uuid5

from app.modules.research.datasets.models import Dataset, DatasetPreview
from app.modules.research.datasets.sqlite_repository import SQLiteDatasetRepository
from app.modules.research.datasets.use_cases import DatasetService
from app.modules.research.documents.models import Document
from app.modules.research.documents.sqlite_repository import SQLiteDocumentRepository
from app.modules.research.documents.use_cases import DocumentService
from app.modules.research.instrument.contracts import InstrumentContext
from app.modules.research.instrument.models import (
    DatasetMapping,
    InstrumentConfirmation,
    InstrumentDimension,
    InstrumentIndicator,
    InstrumentItem,
    InstrumentProvenance,
    InstrumentVariable,
    ItemColumnMapping,
    ResponseOption,
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
from app.modules.research.projects.models import Project
from app.modules.research.projects.sqlite_repository import SQLiteProjectRepository
from app.modules.research.projects.use_cases import ProjectService


def standard_likert_options() -> list[ResponseOption]:
    return [
        ResponseOption(code="1", label="Totalmente en desacuerdo", numeric_value=1.0),
        ResponseOption(code="2", label="En desacuerdo", numeric_value=2.0),
        ResponseOption(code="3", label="Neutral", numeric_value=3.0),
        ResponseOption(code="4", label="De acuerdo", numeric_value=4.0),
        ResponseOption(code="5", label="Totalmente de acuerdo", numeric_value=5.0),
    ]


# Fixture 1: Instrumento válido confirmado con dos ítems, uno de ellos invertido
def make_valid_confirmed_instrument() -> InstrumentContext:
    var_id = uuid4()
    dim_id = uuid4()
    ind_id = uuid4()
    item1_id = uuid4()
    item2_id = uuid4()
    rule_id = uuid4()
    inst_id = uuid4()
    dataset_id = uuid4()
    created = datetime(2026, 11, 1, 10, 0, tzinfo=UTC)
    confirmed_dt = datetime(2026, 11, 2, 12, 30, tzinfo=UTC)
    updated = confirmed_dt

    return InstrumentContext(
        schema_version="1.0.0",
        instrument_id=inst_id,
        project_id=uuid4(),
        version=1,
        status="reviewed",
        created_at=created,
        updated_at=updated,
        provenance=InstrumentProvenance(
            source_kind="document",
            source_document_id=uuid4(),
            source_document_hash="a" * 64,
            methodology_review_id=uuid4(),
            methodology_review_version=1,
            methodology_review_hash="b" * 64,
        ),
        confirmation=InstrumentConfirmation(
            state="confirmed",
            confirmed_at=confirmed_dt,
            confirmer_ref="revisor_metodologico",
        ),
        variables=[
            InstrumentVariable(
                variable_id=var_id,
                name="Clima Laboral",
                scale="ordinal",
                methodology_variable_id=uuid4(),
            )
        ],
        dimensions=[
            InstrumentDimension(
                dimension_id=dim_id,
                variable_id=var_id,
                name="Comunicación Interna",
            )
        ],
        indicators=[
            InstrumentIndicator(
                indicator_id=ind_id,
                dimension_id=dim_id,
                name="Claridad de Información",
            )
        ],
        items=[
            InstrumentItem(
                item_id=item1_id,
                variable_id=var_id,
                dimension_id=dim_id,
                indicator_id=ind_id,
                text="La comunicación de la dirección es oportuna y clara.",
                response_type="single_choice",
                response_options=standard_likert_options(),
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
                response_options=standard_likert_options(),
                valid_min=1.0,
                valid_max=5.0,
                reverse_scored=True,
                reverse_rule="min_plus_max_minus_value",
            ),
        ],
        scoring_rules=[
            ScoringRule(
                scoring_rule_id=rule_id,
                scope="dimension",
                dimension_id=dim_id,
                item_ids=[item1_id, item2_id],
                aggregation="sum",
                missing_policy="all_required",
                confirmed=True,
            )
        ],
        dataset_mapping=DatasetMapping(
            dataset_id=dataset_id,
            dataset_hash="c" * 64,
            instrument_version=1,
            item_columns=[
                ItemColumnMapping(item_id=item1_id, column_name="p1_comunicacion_directa"),
                ItemColumnMapping(item_id=item2_id, column_name="p2_info_contradictoria"),
            ],
            status="confirmed",
            confirmation=InstrumentConfirmation(
                state="confirmed",
                confirmed_at=confirmed_dt,
                confirmer_ref="revisor_metodologico",
            ),
        ),
    )


# Fixture 2: Ítem invertido sin rango válido declarado
def make_inverted_item_without_range() -> dict:
    return {
        "item_id": uuid4(),
        "variable_id": uuid4(),
        "dimension_id": uuid4(),
        "indicator_id": uuid4(),
        "text": "Ítem invertido sin rango declarado.",
        "response_type": "single_choice",
        "response_options": standard_likert_options(),
        "valid_min": None,
        "valid_max": None,
        "reverse_scored": True,
        "reverse_rule": "min_plus_max_minus_value",
    }


# Fixture 3: Alternativas de respuesta con códigos duplicados
def make_duplicate_response_options() -> dict:
    return {
        "item_id": uuid4(),
        "variable_id": uuid4(),
        "dimension_id": uuid4(),
        "indicator_id": uuid4(),
        "text": "Ítem con opciones duplicadas.",
        "response_type": "single_choice",
        "response_options": [
            ResponseOption(code="A", label="Opción 1", numeric_value=1.0),
            ResponseOption(code="A", label="Opción 2", numeric_value=2.0),
        ],
    }


# Fixture 4: Referencias jerárquicas inválidas (dimensión no pertenece a la variable)
def make_invalid_hierarchy_references() -> tuple[
    list[InstrumentVariable],
    list[InstrumentDimension],
    list[InstrumentIndicator],
    list[InstrumentItem],
]:
    var1_id = uuid4()
    var2_id = uuid4()
    dim1_id = uuid4()
    ind1_id = uuid4()

    variables = [
        InstrumentVariable(variable_id=var1_id, name="Variable 1"),
        InstrumentVariable(variable_id=var2_id, name="Variable 2"),
    ]
    dimensions = [
        InstrumentDimension(dimension_id=dim1_id, variable_id=var1_id, name="Dimensión 1"),
    ]
    indicators = [
        InstrumentIndicator(indicator_id=ind1_id, dimension_id=dim1_id, name="Indicador 1"),
    ]
    items = [
        InstrumentItem(
            item_id=uuid4(),
            variable_id=var2_id,  # Discrepancia intencional con dim1 (pertenece a var1)
            dimension_id=dim1_id,
            indicator_id=ind1_id,
            text="Pregunta con jerarquía desalineada.",
            response_type="numeric",
            valid_min=0.0,
            valid_max=10.0,
        )
    ]
    return variables, dimensions, indicators, items


# Fixture 5: Regla de puntuación que mezcla dimensiones o apunta a un target inexistente
def make_cross_dimensional_scoring_rule(
    valid_instrument: InstrumentContext,
) -> ScoringRule:
    fake_dim_id = uuid4()  # No existe en el instrumento
    return ScoringRule(
        scoring_rule_id=uuid4(),
        scope="dimension",
        dimension_id=fake_dim_id,
        item_ids=[valid_instrument.items[0].item_id],
        aggregation="mean",
        missing_policy="all_required",
        confirmed=True,
    )


# Fixture 6: Mapeo incompleto confirmado (falta cubrir un ítem)
def make_incomplete_mapping_confirmed(
    valid_instrument: InstrumentContext,
) -> DatasetMapping:
    # Solo mapea el primer ítem, dejando el segundo fuera
    first_item = valid_instrument.items[0]
    return DatasetMapping(
        dataset_id=uuid4(),
        dataset_hash="d" * 64,
        instrument_version=valid_instrument.version,
        item_columns=[
            ItemColumnMapping(item_id=first_item.item_id, column_name="columna_1"),
        ],
        status="confirmed",
        confirmation=InstrumentConfirmation(
            state="confirmed",
            confirmed_at=datetime.now(UTC),
            confirmer_ref="revisor",
        ),
    )


# Fixture 7: Columna de dataset duplicada en dos ítems
def make_duplicate_column_mapping(item1_id: UUID, item2_id: UUID) -> dict:
    return {
        "dataset_id": uuid4(),
        "dataset_hash": "e" * 64,
        "instrument_version": 1,
        "item_columns": [
            ItemColumnMapping(item_id=item1_id, column_name="columna_compartida"),
            ItemColumnMapping(item_id=item2_id, column_name="columna_compartida"),
        ],
        "status": "draft",
    }


# Fixture 8: Mapeo marcado como confirmado pero sin confirmación humana explícita
def make_confirmed_mapping_unauthorized(item_id: UUID) -> dict:
    return {
        "dataset_id": uuid4(),
        "dataset_hash": "f" * 64,
        "instrument_version": 1,
        "item_columns": [
            ItemColumnMapping(item_id=item_id, column_name="columna_valida"),
        ],
        "status": "confirmed",
        "confirmation": InstrumentConfirmation(state="pending"),
    }


# Fixture 9: Versión de instrumento incompatible en el mapeo
def make_incompatible_instrument_version(
    valid_instrument: InstrumentContext,
) -> DatasetMapping:
    return DatasetMapping(
        dataset_id=uuid4(),
        dataset_hash="a" * 64,
        instrument_version=valid_instrument.version + 99,  # Incompatible
        item_columns=[
            ItemColumnMapping(item_id=it.item_id, column_name=f"col_{i}")
            for i, it in enumerate(valid_instrument.items)
        ],
        status="draft",
    )


# Fixture 10: Instrumento válido revisado sin dataset asociado
def make_valid_reviewed_without_dataset() -> InstrumentContext:
    var_id = uuid4()
    dim_id = uuid4()
    ind_id = uuid4()
    item_id = uuid4()
    rule_id = uuid4()
    created = datetime(2026, 11, 3, 8, 0, tzinfo=UTC)
    confirmed_dt = datetime(2026, 11, 3, 9, 15, tzinfo=UTC)
    updated = confirmed_dt

    return InstrumentContext(
        schema_version="1.0.0",
        instrument_id=uuid4(),
        project_id=uuid4(),
        version=1,
        status="reviewed",
        created_at=created,
        updated_at=updated,
        provenance=InstrumentProvenance(
            source_kind="manual",
            methodology_review_id=uuid4(),
            methodology_review_version=1,
            methodology_review_hash="d" * 64,
        ),
        confirmation=InstrumentConfirmation(
            state="confirmed",
            confirmed_at=confirmed_dt,
            confirmer_ref="auditor_investigacion",
        ),
        variables=[
            InstrumentVariable(
                variable_id=var_id,
                name="Autoeficacia",
                scale="interval",
                methodology_variable_id=uuid4(),
            )
        ],
        dimensions=[
            InstrumentDimension(
                dimension_id=dim_id,
                variable_id=var_id,
                name="Confianza en Tareas Complejas",
            )
        ],
        indicators=[
            InstrumentIndicator(
                indicator_id=ind_id,
                dimension_id=dim_id,
                name="Persistencia",
            )
        ],
        items=[
            InstrumentItem(
                item_id=item_id,
                variable_id=var_id,
                dimension_id=dim_id,
                indicator_id=ind_id,
                text="Puedo resolver problemas difíciles si me esfuerzo lo suficiente.",
                response_type="single_choice",
                response_options=standard_likert_options(),
                valid_min=1.0,
                valid_max=5.0,
                reverse_scored=False,
            )
        ],
        scoring_rules=[
            ScoringRule(
                scoring_rule_id=rule_id,
                scope="dimension",
                dimension_id=dim_id,
                item_ids=[item_id],
                aggregation="mean",
                missing_policy="all_required",
                confirmed=True,
            )
        ],
        dataset_mapping=None,
    )


# =============================================================================
# DETERMINISTIC CONTRACTUAL FIXTURES GENERATION (v1.0.0)
# =============================================================================

SEED_NAMESPACE = uuid5(NAMESPACE_DNS, "tesisstat.ai.contract.fixtures")


def deterministic_uuid(name: str) -> UUID:
    """Deriva un UUID5 determinista y reproducible a partir de un identificador textual."""
    return uuid5(SEED_NAMESPACE, name)


FIXED_BASE_TIME = datetime(2026, 11, 1, 10, 0, 0, tzinfo=UTC)


def make_deterministic_clock(
    start: datetime = FIXED_BASE_TIME, step_seconds: int = 60
) -> Callable[[], datetime]:
    """Generador de reloj controlado y monotónico determinista."""
    current = start

    def _clock() -> datetime:
        nonlocal current
        val = current
        current = current + timedelta(seconds=step_seconds)
        return val

    return _clock


# Documentos y datasets sintéticos fijos con contenido inmutable
CONFIRMED_DOC_CONTENT = (
    b"%PDF-1.4\nCuestionario de Clima Laboral y Desempeno Organizacional 2026\n%%EOF"
)
CONFIRMED_DATASET_CONTENT = (
    b"p1_comunicacion_directa,p2_info_contradictoria\n1,5\n2,4\n3,3\n4,2\n5,1\n"
)

REVIEWED_DOC_CONTENT = b"%PDF-1.4\nEscala de Autoeficacia Percibida en Investigacion 2026\n%%EOF"


def create_deterministic_harness(
    tmp_path: Path,
    clock: Callable[[], datetime] | None = None,
) -> dict[str, Any]:
    """Crea un arnés SQLite temporal para ejecución determinista del ciclo de vida."""
    db_path = tmp_path / "research_contract.db"
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
        clock=clock,
    )
    reader = ResearchInstrumentContextReader(service)

    return {
        "db_path": db_path,
        "storage_path": storage_path,
        "project_repo": project_repo,
        "projects": projects,
        "doc_repo": doc_repo,
        "documents": documents,
        "dataset_repo": dataset_repo,
        "datasets": datasets,
        "methodology": methodology_repo,
        "instrument_repo": instrument_repo,
        "service": service,
        "reader": reader,
    }


def _build_confirmed_in_dir(tmp_path: Path, clock_start: datetime) -> InstrumentContext:
    clock = make_deterministic_clock(start=clock_start, step_seconds=60)
    h = create_deterministic_harness(tmp_path, clock=clock)

    project_id = deterministic_uuid("project:clima")
    project = Project(
        id=project_id,
        title="Investigación de Clima y Desempeño",
        description="Proyecto sintético determinista para validación contractual",
        university="Universidad Nacional Mayor de San Marcos",
        faculty="Facultad de Psicología",
        program="Psicología Organizacional",
        degree="bachelor",
        academic_year=2026,
        created_at=clock_start,
        updated_at=clock_start,
    )
    h["project_repo"].add(project)

    doc_id = deterministic_uuid("document:clima")
    doc = Document(
        id=doc_id,
        project_id=project_id,
        name="cuestionario_clima.pdf",
        format="pdf",
        size=len(CONFIRMED_DOC_CONTENT),
        uploaded_at=clock_start,
    )
    h["doc_repo"].add(doc, CONFIRMED_DOC_CONTENT)

    meth_var_id = deterministic_uuid("meth_var:clima")
    finding = ReviewFinding(
        value="Clima Laboral",
        kind="quotation",
        evidence=["Cuestionario de Clima Laboral y Desempeño Organizacional"],
    )
    review = MethodologyReview(
        project_id=project_id,
        document_id=doc_id,
        origin="manual",
        content=ReviewContent(
            title=ReviewFinding(value="Investigación de Clima y Desempeño", kind="manual"),
            variables=[
                ReviewVariable(
                    id=meth_var_id,
                    name=finding,
                )
            ],
        ),
        pending_fields=[],
        review_status="reviewed",
        version=1,
        updated_at=clock_start,
        reviewed_at=clock_start,
    )
    h["methodology"].save_review(review, expected_version=None)

    dataset_id = deterministic_uuid("dataset:clima")
    dataset = Dataset(
        id=dataset_id,
        project_id=project_id,
        name="clima_dataset.csv",
        format="csv",
        size=len(CONFIRMED_DATASET_CONTENT),
        row_count=5,
        column_count=2,
        columns=["p1_comunicacion_directa", "p2_info_contradictoria"],
        uploaded_at=clock_start,
        active=True,
    )
    preview = DatasetPreview(
        columns=["p1_comunicacion_directa", "p2_info_contradictoria"],
        rows=[
            ["1", "5"],
            ["2", "4"],
            ["3", "3"],
            ["4", "2"],
            ["5", "1"],
        ],
        row_count=5,
        column_count=2,
        format="csv",
        warnings=[],
    )
    h["dataset_repo"].add(dataset, preview, CONFIRMED_DATASET_CONTENT)
    h["dataset_repo"].activate(project_id, dataset_id)

    var_id = deterministic_uuid("var:clima")
    dim_id = deterministic_uuid("dim:comunicacion")
    ind_id = deterministic_uuid("ind:claridad")
    item1_id = deterministic_uuid("item:p1")
    item2_id = deterministic_uuid("item:p2")
    rule_id = deterministic_uuid("rule:sum_comunicacion")
    inst_id = deterministic_uuid("instrument:clima")

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

    h["service"].create_draft(
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
        instrument_id=inst_id,
    )

    h["service"].link_methodology(
        project_id,
        inst_id,
        expected_version=0,
        document_id=doc_id,
        variable_links={var_id: meth_var_id},
    )

    h["service"].confirm_scoring_rules(project_id, inst_id, expected_version=1)

    h["service"].set_mapping(
        project_id,
        inst_id,
        expected_version=2,
        dataset_id=dataset_id,
        item_columns=[
            ItemColumnMapping(item_id=item1_id, column_name="p1_comunicacion_directa"),
            ItemColumnMapping(item_id=item2_id, column_name="p2_info_contradictoria"),
        ],
    )

    h["service"].confirm_mapping(
        project_id, inst_id, expected_version=3, confirmer_ref="revisor_metodologico"
    )

    h["service"].confirm_instrument(
        project_id, inst_id, expected_version=4, confirmer_ref="revisor_metodologico"
    )

    return h["reader"].get_confirmed_context(str(project_id), str(inst_id))


def build_deterministic_confirmed_instrument_with_mapping(
    storage_dir: Path | None = None,
    clock_start: datetime = FIXED_BASE_TIME,
) -> InstrumentContext:
    """Genera determinísticamente el fixture contractual de instrumento confirmado con mapeo."""
    if storage_dir is None:
        with tempfile.TemporaryDirectory() as td:
            return _build_confirmed_in_dir(Path(td), clock_start)
    return _build_confirmed_in_dir(storage_dir, clock_start)


def _build_reviewed_in_dir(tmp_path: Path, clock_start: datetime) -> InstrumentContext:
    clock = make_deterministic_clock(start=clock_start, step_seconds=60)
    h = create_deterministic_harness(tmp_path, clock=clock)

    project_id = deterministic_uuid("project:autoeficacia")
    project = Project(
        id=project_id,
        title="Estudio de Autoeficacia en Investigadores",
        description="Proyecto sintético determinista para validación contractual",
        university="Universidad Nacional Mayor de San Marcos",
        faculty="Facultad de Educación",
        program="Investigación Educativa",
        degree="master",
        academic_year=2026,
        created_at=clock_start,
        updated_at=clock_start,
    )
    h["project_repo"].add(project)

    doc_id = deterministic_uuid("document:autoeficacia")
    doc = Document(
        id=doc_id,
        project_id=project_id,
        name="escala_autoeficacia.pdf",
        format="pdf",
        size=len(REVIEWED_DOC_CONTENT),
        uploaded_at=clock_start,
    )
    h["doc_repo"].add(doc, REVIEWED_DOC_CONTENT)

    meth_var_id = deterministic_uuid("meth_var:autoeficacia")
    finding = ReviewFinding(
        value="Autoeficacia Académica",
        kind="quotation",
        evidence=["Escala de Autoeficacia Percibida en Investigadores"],
    )
    review = MethodologyReview(
        project_id=project_id,
        document_id=doc_id,
        origin="manual",
        content=ReviewContent(
            title=ReviewFinding(value="Estudio de Autoeficacia", kind="manual"),
            variables=[
                ReviewVariable(
                    id=meth_var_id,
                    name=finding,
                )
            ],
        ),
        pending_fields=[],
        review_status="reviewed",
        version=1,
        updated_at=clock_start,
        reviewed_at=clock_start,
    )
    h["methodology"].save_review(review, expected_version=None)

    var_id = deterministic_uuid("var:autoeficacia")
    dim_id = deterministic_uuid("dim:confianza")
    ind_id = deterministic_uuid("ind:persistencia")
    item_id = deterministic_uuid("item:autoeficacia_1")
    rule_id = deterministic_uuid("rule:mean_autoeficacia")
    inst_id = deterministic_uuid("instrument:autoeficacia")

    opts = standard_likert_options()
    items = [
        InstrumentItem(
            item_id=item_id,
            variable_id=var_id,
            dimension_id=dim_id,
            indicator_id=ind_id,
            text="Puedo resolver problemas difíciles si me esfuerzo lo suficiente.",
            response_type="single_choice",
            response_options=opts,
            valid_min=1.0,
            valid_max=5.0,
            reverse_scored=False,
        )
    ]
    rules = [
        ScoringRule(
            scoring_rule_id=rule_id,
            scope="dimension",
            dimension_id=dim_id,
            item_ids=[item_id],
            aggregation="mean",
            missing_policy="all_required",
            confirmed=False,
        )
    ]

    h["service"].create_draft(
        project_id,
        variables=[InstrumentVariable(variable_id=var_id, name="Autoeficacia", scale="interval")],
        dimensions=[
            InstrumentDimension(
                dimension_id=dim_id, variable_id=var_id, name="Confianza en Tareas Complejas"
            )
        ],
        indicators=[
            InstrumentIndicator(indicator_id=ind_id, dimension_id=dim_id, name="Persistencia")
        ],
        items=items,
        scoring_rules=rules,
        instrument_id=inst_id,
    )

    h["service"].link_methodology(
        project_id,
        inst_id,
        expected_version=0,
        document_id=doc_id,
        variable_links={var_id: meth_var_id},
    )

    h["service"].confirm_scoring_rules(project_id, inst_id, expected_version=1)

    h["service"].confirm_instrument(
        project_id, inst_id, expected_version=2, confirmer_ref="auditor_investigacion"
    )

    return h["reader"].get_confirmed_context(str(project_id), str(inst_id))


def build_deterministic_reviewed_instrument_without_mapping(
    storage_dir: Path | None = None,
    clock_start: datetime = FIXED_BASE_TIME,
) -> InstrumentContext:
    """Genera determinísticamente el fixture contractual de instrumento revisado sin mapeo."""
    if storage_dir is None:
        with tempfile.TemporaryDirectory() as td:
            return _build_reviewed_in_dir(Path(td), clock_start)
    return _build_reviewed_in_dir(storage_dir, clock_start)
