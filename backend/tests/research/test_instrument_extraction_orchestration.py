"""Deterministic test suite for InstrumentExtractionService (Sesión 18A-4.3).

Tests 24 positive, negative, and edge cases covering:
1. Complete DOCX questionnaire extraction.
2. PDF identifiable instrument extraction.
3. Multiple instruments within the same document.
4. Structurally valid instrument without scoring rules.
5. Valid candidate converted into a persisted draft.
6. Decoupled provenance: methodology and instrument in separate documents.
7. SHA-256 hash integrity in provenance.
8. Idempotency: repeated extraction avoids duplicate drafts.
9. Nonexistent or foreign project document.
10. Insufficient text / no_text extraction.
11. Failed extraction.
12. Truncated document text.
13. Incomplete fragmentation / no patterns detected.
14. Unknown dimension / missing dimension reference.
15. Response alternatives without verifiable numeric values.
16. Incomplete scoring rule.
17. Missing, invalid, or ambiguous citations.
18. Invalid JSON response from provider.
19. Quota and timeout errors from AI provider.
20. Unconfigured provider.
21. External invocation attempt without explicit consent.
22. Source document deleted, modified, or storage error in check_stale.
23. Outdated methodology review in check_stale.
24. Backward-compatible legacy link_methodology calls.
"""

from __future__ import annotations

import hashlib
import io
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from docx import Document as WordDocument
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from app.modules.research.datasets.sqlite_repository import SQLiteDatasetRepository
from app.modules.research.datasets.use_cases import DatasetService
from app.modules.research.documents.extraction import (
    ExtractionLimits,
    ExtractionResult,
    ExtractionService,
)
from app.modules.research.documents.sqlite_repository import SQLiteDocumentRepository
from app.modules.research.documents.use_cases import DocumentNotFound, DocumentService
from app.modules.research.instrument.contracts import InstrumentContext
from app.modules.research.instrument.extraction_models import (
    CandidateInstrument,
    ExtractedDimension,
    ExtractedIndicator,
    ExtractedItem,
    ExtractedResponseOption,
    ExtractedScoringRule,
    ExtractedVariable,
)
from app.modules.research.instrument.extraction_provider import (
    FixtureInstrumentProvider,
    InstrumentExtractionProvider,
)
from app.modules.research.instrument.extraction_service import (
    DocumentExtractionConsentRequired,
    IncompleteCandidateError,
    InstrumentExtractionService,
)
from app.modules.research.instrument.models import (
    InstrumentDimension,
    InstrumentIndicator,
    InstrumentItem,
    InstrumentVariable,
    ResponseOption,
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
from app.shared.ai_errors import AIError

# --- Test Helpers & Synthetic File Builders ---


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _build_pdf_bytes(text: str) -> bytes:
    writer = PdfWriter()
    page = writer.add_blank_page(width=300, height=300)
    font = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        }
    )
    page[NameObject("/Resources")] = DictionaryObject(
        {NameObject("/Font"): DictionaryObject({NameObject("/F1"): writer._add_object(font)})}
    )
    stream = DecodedStreamObject()
    # Simple ASCII stream Tj
    safe_text = "".join(c if ord(c) < 128 else " " for c in text)
    stream.set_data(f"BT /F1 10 Tf 20 250 Td ({safe_text}) Tj ET".encode("latin-1", "ignore"))
    page[NameObject("/Contents")] = writer._add_object(stream)
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def _build_docx_bytes(paragraphs: list[str], table_rows: list[list[str]] | None = None) -> bytes:
    doc = WordDocument()
    for p in paragraphs:
        doc.add_paragraph(p)
    if table_rows:
        table = doc.add_table(rows=len(table_rows), cols=len(table_rows[0]))
        for r_idx, row in enumerate(table_rows):
            for c_idx, val in enumerate(row):
                table.cell(r_idx, c_idx).text = val
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def _setup_harness(tmp_path):
    db_path = tmp_path / "test_research.db"
    storage_path = tmp_path / "storage"
    storage_path.mkdir(parents=True, exist_ok=True)

    project_repo = SQLiteProjectRepository(db_path)
    projects = ProjectService(project_repo)

    doc_repo = SQLiteDocumentRepository(db_path, storage_path / "docs")
    documents = DocumentService(doc_repo, projects)

    dataset_repo = SQLiteDatasetRepository(db_path, storage_path / "datasets")
    datasets = DatasetService(dataset_repo, projects)

    extraction_service = ExtractionService(
        doc_repo,
        doc_repo,
        projects,
        ExtractionLimits(
            max_pages=50,
            max_units=5000,
            max_characters=100000,
            max_content_bytes=5 * 1024 * 1024,
        ),
    )

    methodology_repo = SQLiteMethodologyRepository(db_path)
    instrument_repo = SQLiteInstrumentRepository(db_path)

    instrument_service = InstrumentService(
        repository=instrument_repo,
        projects=projects,
        documents=documents,
        methodology=methodology_repo,
        datasets=datasets,
    )

    return {
        "db_path": db_path,
        "storage_path": storage_path,
        "projects": projects,
        "doc_repo": doc_repo,
        "documents": documents,
        "datasets": datasets,
        "extraction_service": extraction_service,
        "methodology_repo": methodology_repo,
        "instrument_repo": instrument_repo,
        "instrument_service": instrument_service,
    }


def _seed_project(harness):
    return harness["projects"].create(
        ProjectDraft(
            title="Investigación de Eficacia Docente",
            university="Universidad Nacional",
            program="Educación",
            degree="bachelor",
        )
    )


def _seed_reviewed_methodology(harness, project_id: UUID, document_id: UUID, var_name="Desempeño"):
    var_id = uuid4()
    content = ReviewContent(
        title=ReviewFinding(value="Estudio de Eficacia", kind="manual"),
        general_objective=ReviewFinding(value="Evaluar el desempeño docente", kind="manual"),
        research_design=ReviewFinding(value="Descriptivo correlacional", kind="manual"),
        variables=[
            ReviewVariable(
                id=var_id,
                name=ReviewFinding(value=var_name, kind="manual"),
            )
        ],
    )
    rev = MethodologyReview(
        project_id=project_id,
        document_id=document_id,
        origin="manual",
        content=content,
        pending_fields=[],
        version=1,
        review_status="reviewed",
        updated_at=datetime.now(UTC),
        reviewed_at=datetime.now(UTC),
    )
    harness["methodology_repo"].save_review(rev, expected_version=None)
    return rev, var_id


# --- FASE 8: TEST CASES ---


def test_1_docx_with_complete_questionnaire(tmp_path):
    """1. Documento DOCX con un cuestionario completo."""
    h = _setup_harness(tmp_path)
    proj = _seed_project(h)

    docx_text_p1 = "ANEXO 1: CUESTIONARIO DE DESEMPEÑO DOCENTE"
    docx_text_p2 = "Escala de medición: 1 = Nunca, 2 = A veces, 3 = Siempre"
    table = [
        ["N°", "Ítem", "1", "2", "3"],
        ["1", "El docente planifica sus sesiones de clase oportunamente.", "O", "O", "O"],
        ["2", "El docente utiliza recursos didácticos innovadores.", "O", "O", "O"],
    ]
    data = _build_docx_bytes([docx_text_p1, docx_text_p2], table)
    doc = h["documents"].add(proj.id, "anexo1_cuestionario.docx", data)

    # Provider double returning valid structured extraction
    provider_response = {
        "instruments": [
            {
                "name": "Cuestionario de Desempeño Docente",
                "description": "Instrumento de evaluación docente",
                "target_variable_name": "Desempeño Docente",
                "variables": [
                    {
                        "name": "Desempeño Docente",
                        "role": "dependent",
                        "scale": "ordinal",
                        "evidence_quote": "CUESTIONARIO DE DESEMPEÑO DOCENTE",
                    }
                ],
                "dimensions": [
                    {
                        "name": "Planificación",
                        "evidence_quote": "planifica sus sesiones de clase",
                    }
                ],
                "indicators": [
                    {
                        "name": "Oportunidad",
                        "evidence_quote": "oportunamente",
                    }
                ],
                "items": [
                    {
                        "item_number": 1,
                        "text": "El docente planifica sus sesiones de clase oportunamente.",
                        "variable_name": "Desempeño Docente",
                        "dimension_name": "Planificación",
                        "indicator_name": "Oportunidad",
                        "response_type": "single_choice",
                        "response_options": [
                            {"code": "1", "label": "Nunca", "numeric_value": 1.0},
                            {"code": "2", "label": "A veces", "numeric_value": 2.0},
                            {"code": "3", "label": "Siempre", "numeric_value": 3.0},
                        ],
                        "source_quote": "El docente planifica sus sesiones de clase oportunamente.",
                    },
                    {
                        "item_number": 2,
                        "text": "El docente utiliza recursos didácticos innovadores.",
                        "variable_name": "Desempeño Docente",
                        "dimension_name": "Planificación",
                        "indicator_name": "Oportunidad",
                        "response_type": "single_choice",
                        "response_options": [
                            {"code": "1", "label": "Nunca", "numeric_value": 1.0},
                            {"code": "2", "label": "A veces", "numeric_value": 2.0},
                            {"code": "3", "label": "Siempre", "numeric_value": 3.0},
                        ],
                        "source_quote": "El docente utiliza recursos didácticos innovadores.",
                    },
                ],
                "scoring_rules": [],
                "warnings": [],
            }
        ],
        "warnings": [],
    }

    fixture_provider = FixtureInstrumentProvider(default_response=provider_response)
    service = InstrumentExtractionService(
        projects=h["projects"],
        documents=h["documents"],
        extraction_service=h["extraction_service"],
        provider=fixture_provider,
        instrument_service=h["instrument_service"],
    )

    result = service.extract(proj.id, doc.id)

    assert result.status == "completed"
    assert len(result.instruments) == 1
    cand = result.instruments[0]
    assert cand.name == "Cuestionario de Desempeño Docente"
    assert cand.is_complete is True
    assert len(cand.items) == 2
    # Check verifiable citations
    assert len(result.evidences) > 0
    assert any(e.verified for e in result.evidences)


def test_2_pdf_with_identifiable_instrument(tmp_path):
    """2. Texto PDF con un instrumento identificable."""
    h = _setup_harness(tmp_path)
    proj = _seed_project(h)

    pdf_content = (
        "ANEXO 2: ESCALA DE LIKERT DE SATISFACCION\n"
        "1. El servicio de biblioteca satisface mis requerimientos.\n"
        "2. El personal de atencion resuelve mis dudas con amabilidad.\n"
        "Alternativas: 1 = En desacuerdo, 2 = De acuerdo\n"
    )
    data = _build_pdf_bytes(pdf_content)
    doc = h["documents"].add(proj.id, "escala.pdf", data)

    provider_response = {
        "instruments": [
            {
                "name": "Escala de Likert de Satisfaccion",
                "description": "Evaluación de satisfacción de biblioteca",
                "variables": [
                    {
                        "name": "Satisfaccion",
                        "role": "dependent",
                        "scale": "ordinal",
                        "evidence_quote": "ESCALA DE LIKERT DE SATISFACCION",
                    }
                ],
                "dimensions": [
                    {
                        "name": "Servicio",
                        "evidence_quote": "El servicio de biblioteca",
                    }
                ],
                "indicators": [
                    {
                        "name": "Atencion",
                        "evidence_quote": "El personal de atencion",
                    }
                ],
                "items": [
                    {
                        "item_number": 1,
                        "text": "El servicio de biblioteca satisface mis requerimientos.",
                        "variable_name": "Satisfaccion",
                        "dimension_name": "Servicio",
                        "indicator_name": "Atencion",
                        "response_type": "single_choice",
                        "response_options": [
                            {"code": "1", "label": "En desacuerdo", "numeric_value": 1.0},
                            {"code": "2", "label": "De acuerdo", "numeric_value": 2.0},
                        ],
                        "source_quote": "El servicio de biblioteca satisface mis requerimientos.",
                    }
                ],
                "scoring_rules": [],
                "warnings": [],
            }
        ],
        "warnings": [],
    }

    fixture_provider = FixtureInstrumentProvider(default_response=provider_response)
    service = InstrumentExtractionService(
        projects=h["projects"],
        documents=h["documents"],
        extraction_service=h["extraction_service"],
        provider=fixture_provider,
        instrument_service=h["instrument_service"],
    )

    result = service.extract(proj.id, doc.id)
    assert result.status == "completed"
    assert len(result.instruments) == 1
    assert result.instruments[0].name == "Escala de Likert de Satisfaccion"


def test_3_two_separate_instruments_in_same_document(tmp_path):
    """3. Dos instrumentos separados dentro del mismo documento."""
    h = _setup_harness(tmp_path)
    proj = _seed_project(h)

    doc_text = (
        "ANEXO 1: CUESTIONARIO DE CLIMA LABORAL\n"
        "1. Existe comunicacion fluida entre las diferentes areas.\n"
        "\n"
        "ANEXO 2: INVENTARIO DE BURNOUT ACADEMICO\n"
        "1. Siento cansancio emocional al finalizar la jornada de trabajo.\n"
    )
    data = _build_docx_bytes([doc_text])
    doc = h["documents"].add(proj.id, "anexos_multiples.docx", data)

    provider_response = {
        "instruments": [
            {
                "name": "Cuestionario de Clima Laboral",
                "variables": [
                    {
                        "name": "Clima",
                        "evidence_quote": "CUESTIONARIO DE CLIMA LABORAL",
                    }
                ],
                "dimensions": [{"name": "Comunicacion", "evidence_quote": "comunicacion fluida"}],
                "indicators": [{"name": "Fluidez", "evidence_quote": "fluida"}],
                "items": [
                    {
                        "item_number": 1,
                        "text": "Existe comunicacion fluida entre las diferentes areas.",
                        "variable_name": "Clima",
                        "dimension_name": "Comunicacion",
                        "indicator_name": "Fluidez",
                        "response_type": "single_choice",
                        "response_options": [
                            {"code": "1", "label": "No", "numeric_value": 0.0},
                            {"code": "2", "label": "Si", "numeric_value": 1.0},
                        ],
                        "source_quote": "Existe comunicacion fluida entre las diferentes areas.",
                    }
                ],
                "scoring_rules": [],
                "warnings": [],
            },
            {
                "name": "Inventario de Burnout Academico",
                "variables": [
                    {
                        "name": "Burnout",
                        "evidence_quote": "INVENTARIO DE BURNOUT ACADEMICO",
                    }
                ],
                "dimensions": [
                    {
                        "name": "Agotamiento",
                        "evidence_quote": "cansancio emocional",
                    }
                ],
                "indicators": [{"name": "Emocional", "evidence_quote": "emocional"}],
                "items": [
                    {
                        "item_number": 1,
                        "text": "Siento cansancio emocional al finalizar la jornada de trabajo.",
                        "variable_name": "Burnout",
                        "dimension_name": "Agotamiento",
                        "indicator_name": "Emocional",
                        "response_type": "single_choice",
                        "response_options": [
                            {"code": "1", "label": "Nunca", "numeric_value": 1.0},
                            {"code": "2", "label": "Siempre", "numeric_value": 2.0},
                        ],
                        "source_quote": (
                            "Siento cansancio emocional al finalizar la jornada de trabajo."
                        ),
                    }
                ],
                "scoring_rules": [],
                "warnings": [],
            },
        ],
        "warnings": [],
    }

    service = InstrumentExtractionService(
        projects=h["projects"],
        documents=h["documents"],
        extraction_service=h["extraction_service"],
        provider=FixtureInstrumentProvider(default_response=provider_response),
        instrument_service=h["instrument_service"],
    )

    result = service.extract(proj.id, doc.id)
    assert result.status == "completed"
    assert len(result.instruments) == 2
    assert result.instruments[0].name == "Cuestionario de Clima Laboral"
    assert result.instruments[1].name == "Inventario de Burnout Academico"


def test_4_structurally_valid_instrument_without_scoring():
    """4. Instrumento estructuralmente válido sin scoring."""
    v_id = uuid4()
    d_id = uuid4()
    ind_id = uuid4()
    cand = CandidateInstrument(
        name="Cuestionario Sin Scoring",
        variables=[ExtractedVariable(variable_id=v_id, name="Variable A")],
        dimensions=[ExtractedDimension(dimension_id=d_id, variable_id=v_id, name="Dimensión A")],
        indicators=[ExtractedIndicator(indicator_id=ind_id, dimension_id=d_id, name="Indicador A")],
        items=[
            ExtractedItem(
                variable_id=v_id,
                dimension_id=d_id,
                indicator_id=ind_id,
                text="¿Pregunta de prueba?",
                response_type="single_choice",
                response_options=[
                    ExtractedResponseOption(code="1", label="Bajo", numeric_value=1.0),
                    ExtractedResponseOption(code="2", label="Alto", numeric_value=2.0),
                ],
            )
        ],
        scoring_rules=[],  # Intentionally empty
    )

    assert cand.is_complete is True
    assert cand.is_structurally_complete is True
    assert cand.has_operational_scoring is False


def test_5_valid_candidate_converted_to_persisted_draft(tmp_path):
    """5. Candidato válido convertido a borrador real."""
    h = _setup_harness(tmp_path)
    proj = _seed_project(h)

    text = "ANEXO 1: TEST DE PRUEBA\n1. Enunciado de prueba uno.\n"
    data = _build_docx_bytes([text])
    doc = h["documents"].add(proj.id, "test.docx", data)

    v_id = uuid4()
    d_id = uuid4()
    ind_id = uuid4()
    it_id = uuid4()

    cand = CandidateInstrument(
        name="Test de Prueba",
        variables=[ExtractedVariable(variable_id=v_id, name="Var 1", scale="ordinal")],
        dimensions=[ExtractedDimension(dimension_id=d_id, variable_id=v_id, name="Dim 1")],
        indicators=[ExtractedIndicator(indicator_id=ind_id, dimension_id=d_id, name="Ind 1")],
        items=[
            ExtractedItem(
                item_id=it_id,
                variable_id=v_id,
                dimension_id=d_id,
                indicator_id=ind_id,
                text="Enunciado de prueba uno.",
                response_type="single_choice",
                response_options=[
                    ExtractedResponseOption(code="1", label="No", numeric_value=0.0),
                    ExtractedResponseOption(code="2", label="Sí", numeric_value=1.0),
                ],
            )
        ],
        scoring_rules=[],
    )

    service = InstrumentExtractionService(
        projects=h["projects"],
        documents=h["documents"],
        extraction_service=h["extraction_service"],
        provider=FixtureInstrumentProvider(),
        instrument_service=h["instrument_service"],
    )

    draft = service.create_draft_from_candidate(proj.id, doc.id, cand)

    assert isinstance(draft, InstrumentContext)
    assert draft.status == "draft"
    assert draft.confirmation.state == "pending"
    assert draft.version == 0
    assert len(draft.items) == 1
    assert draft.items[0].text == "Enunciado de prueba uno."
    # Verify persisted in repository
    persisted = h["instrument_service"].get(proj.id, draft.instrument_id)
    assert persisted.instrument_id == draft.instrument_id


def test_6_methodology_and_instrument_in_separate_files(tmp_path):
    """6. Metodología e instrumento contenidos en archivos diferentes."""
    h = _setup_harness(tmp_path)
    proj = _seed_project(h)

    # doc1: Tesis con Metodología
    tesis_data = _build_docx_bytes(["CAPITULO III: METODOLOGIA DE LA INVESTIGACION"])
    doc_tesis = h["documents"].add(proj.id, "tesis_completa.docx", tesis_data)
    review, m_var_id = _seed_reviewed_methodology(h, proj.id, doc_tesis.id)

    # doc2: Instrumento separado en Anexo
    anexo_data = _build_docx_bytes(
        [
            "ANEXO A: CUESTIONARIO INDEPENDIENTE\n"
            "1. Primera afirmacion evaluativa.\n"
            "Opciones: 1 = Rara vez, 2 = Siempre\n"
        ]
    )
    doc_anexo = h["documents"].add(proj.id, "cuestionario_separado.docx", anexo_data)

    v_id = uuid4()
    d_id = uuid4()
    ind_id = uuid4()
    it_id = uuid4()
    cand = CandidateInstrument(
        name="Cuestionario Independiente",
        variables=[ExtractedVariable(variable_id=v_id, name="Desempeño", scale="ordinal")],
        dimensions=[ExtractedDimension(dimension_id=d_id, variable_id=v_id, name="Dim 1")],
        indicators=[ExtractedIndicator(indicator_id=ind_id, dimension_id=d_id, name="Ind 1")],
        items=[
            ExtractedItem(
                item_id=it_id,
                variable_id=v_id,
                dimension_id=d_id,
                indicator_id=ind_id,
                text="Primera afirmacion evaluativa.",
                response_type="single_choice",
                response_options=[
                    ExtractedResponseOption(code="1", label="Rara vez", numeric_value=1.0),
                    ExtractedResponseOption(code="2", label="Siempre", numeric_value=2.0),
                ],
            )
        ],
        scoring_rules=[],
    )

    service = InstrumentExtractionService(
        projects=h["projects"],
        documents=h["documents"],
        extraction_service=h["extraction_service"],
        provider=FixtureInstrumentProvider(),
        instrument_service=h["instrument_service"],
        methodology=h["methodology_repo"],
    )

    # Create draft indicating methodology comes from doc_tesis while instrument is from doc_anexo
    draft = service.create_draft_from_candidate(
        proj.id,
        doc_anexo.id,
        cand,
        methodology_document_id=doc_tesis.id,
    )

    assert draft.provenance is not None
    assert draft.provenance.source_kind == "document"
    assert draft.provenance.source_document_id == doc_anexo.id
    assert draft.provenance.methodology_review_id == doc_tesis.id
    assert draft.provenance.source_document_id != draft.provenance.methodology_review_id


def test_7_provenance_preserved_with_correct_hashes(tmp_path):
    """7. Procedencia preservada con hashes correctos."""
    h = _setup_harness(tmp_path)
    proj = _seed_project(h)

    tesis_data = _build_docx_bytes(["CAPITULO III: METODOLOGIA DE LA INVESTIGACION"])
    doc_tesis = h["documents"].add(proj.id, "tesis.docx", tesis_data)
    review, m_var_id = _seed_reviewed_methodology(h, proj.id, doc_tesis.id)

    anexo_data = _build_docx_bytes(["ANEXO: CUESTIONARIO\n1. Reactivo uno.\n"])
    doc_anexo = h["documents"].add(proj.id, "anexo.docx", anexo_data)

    v_id = uuid4()
    d_id = uuid4()
    ind_id = uuid4()
    it_id = uuid4()
    cand = CandidateInstrument(
        name="Cuestionario Hash Test",
        variables=[ExtractedVariable(variable_id=v_id, name="Desempeño", scale="ordinal")],
        dimensions=[ExtractedDimension(dimension_id=d_id, variable_id=v_id, name="Dim 1")],
        indicators=[ExtractedIndicator(indicator_id=ind_id, dimension_id=d_id, name="Ind 1")],
        items=[
            ExtractedItem(
                item_id=it_id,
                variable_id=v_id,
                dimension_id=d_id,
                indicator_id=ind_id,
                text="Reactivo uno.",
                response_type="single_choice",
                response_options=[
                    ExtractedResponseOption(code="1", label="Rara vez", numeric_value=1.0),
                    ExtractedResponseOption(code="2", label="Siempre", numeric_value=2.0),
                ],
            )
        ],
        scoring_rules=[],
    )

    service = InstrumentExtractionService(
        projects=h["projects"],
        documents=h["documents"],
        extraction_service=h["extraction_service"],
        provider=FixtureInstrumentProvider(),
        instrument_service=h["instrument_service"],
        methodology=h["methodology_repo"],
    )

    draft = service.create_draft_from_candidate(
        proj.id,
        doc_anexo.id,
        cand,
        methodology_document_id=doc_tesis.id,
    )

    expected_doc_hash = _sha256(anexo_data)
    expected_review_hash = _sha256(review.content.model_dump_json().encode())

    assert draft.provenance is not None
    assert draft.provenance.source_document_hash == expected_doc_hash
    assert draft.provenance.methodology_review_hash == expected_review_hash


def test_8_repeated_extraction_idempotency(tmp_path):
    """8. Repetición de extracción sin duplicar borradores."""
    h = _setup_harness(tmp_path)
    proj = _seed_project(h)

    text = "ANEXO: CUESTIONARIO DE PRUEBA\n1. Pregunta uno.\n"
    data = _build_docx_bytes([text])
    doc = h["documents"].add(proj.id, "instrumento.docx", data)

    v_id = uuid4()
    d_id = uuid4()
    ind_id = uuid4()
    cand = CandidateInstrument(
        name="Cuestionario Repetible",
        variables=[ExtractedVariable(variable_id=v_id, name="Var", scale="ordinal")],
        dimensions=[ExtractedDimension(dimension_id=d_id, variable_id=v_id, name="Dim")],
        indicators=[ExtractedIndicator(indicator_id=ind_id, dimension_id=d_id, name="Ind")],
        items=[
            ExtractedItem(
                variable_id=v_id,
                dimension_id=d_id,
                indicator_id=ind_id,
                text="Pregunta uno.",
                response_type="single_choice",
                response_options=[
                    ExtractedResponseOption(code="1", label="No", numeric_value=0.0),
                    ExtractedResponseOption(code="2", label="Sí", numeric_value=1.0),
                ],
            )
        ],
        scoring_rules=[],
    )

    service = InstrumentExtractionService(
        projects=h["projects"],
        documents=h["documents"],
        extraction_service=h["extraction_service"],
        provider=FixtureInstrumentProvider(),
        instrument_service=h["instrument_service"],
    )

    draft1 = service.create_draft_from_candidate(proj.id, doc.id, cand)
    draft2 = service.create_draft_from_candidate(proj.id, doc.id, cand)

    assert draft1.instrument_id == draft2.instrument_id
    all_drafts = h["instrument_service"].list(proj.id)
    assert len(all_drafts) == 1


def test_9_nonexistent_or_foreign_document(tmp_path):
    """9. Documento inexistente o de otro proyecto."""
    h = _setup_harness(tmp_path)
    proj1 = _seed_project(h)
    proj2 = h["projects"].create(
        ProjectDraft(
            title="Proyecto 2",
            university="Universidad 2",
            program="Prog 2",
            degree="master",
        )
    )

    doc_data = _build_docx_bytes(["Cuestionario privado."])
    doc1 = h["documents"].add(proj1.id, "doc1.docx", doc_data)

    service = InstrumentExtractionService(
        projects=h["projects"],
        documents=h["documents"],
        extraction_service=h["extraction_service"],
        provider=FixtureInstrumentProvider(),
        instrument_service=h["instrument_service"],
    )

    # Document of project 1 accessed via project 2
    with pytest.raises(DocumentNotFound):
        service.extract(proj2.id, doc1.id)

    # Totally nonexistent document
    with pytest.raises(DocumentNotFound):
        service.extract(proj1.id, uuid4())


def test_10_extraction_no_text(tmp_path):
    """10. Extracción no_text."""
    h = _setup_harness(tmp_path)
    proj = _seed_project(h)

    # An empty or unreadable PDF page produces no_text in PDFTextExtractor
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    buf = io.BytesIO()
    writer.write(buf)
    doc = h["documents"].add(proj.id, "escaneado.pdf", buf.getvalue())

    service = InstrumentExtractionService(
        projects=h["projects"],
        documents=h["documents"],
        extraction_service=h["extraction_service"],
        provider=FixtureInstrumentProvider(),
        instrument_service=h["instrument_service"],
    )

    result = service.extract(proj.id, doc.id)
    assert result.status == "insufficient_text"
    assert len(result.instruments) == 0
    assert any("OCR" in w for w in result.warnings)


def test_11_extraction_failed(tmp_path, monkeypatch):
    """11. Extracción fallida."""
    h = _setup_harness(tmp_path)
    proj = _seed_project(h)

    doc = h["documents"].add(proj.id, "corrupto.docx", _build_docx_bytes(["Texto"]))

    # Simulate extraction failure
    def mock_extract(p_id, d_id):
        return ExtractionResult(
            document_id=d_id,
            project_id=p_id,
            status="failed",
            text="",
            character_count=0,
            units_processed=0,
            processed_at=datetime.now(UTC),
            warnings=["Fallo al procesar archivo comprimido."],
            truncated=False,
        )

    monkeypatch.setattr(h["extraction_service"], "extract", mock_extract)

    service = InstrumentExtractionService(
        projects=h["projects"],
        documents=h["documents"],
        extraction_service=h["extraction_service"],
        provider=FixtureInstrumentProvider(),
        instrument_service=h["instrument_service"],
    )

    result = service.extract(proj.id, doc.id)
    assert result.status == "failed"
    assert len(result.instruments) == 0
    assert any("Fallo al procesar" in w for w in result.warnings)


def test_12_truncated_document(tmp_path, monkeypatch):
    """12. Documento truncado."""
    h = _setup_harness(tmp_path)
    proj = _seed_project(h)

    text = "ANEXO 1: CUESTIONARIO TRUNCADO\n1. Pregunta uno.\n"
    doc = h["documents"].add(proj.id, "truncado.docx", _build_docx_bytes([text]))

    def mock_extract(p_id, d_id):
        return ExtractionResult(
            document_id=d_id,
            project_id=p_id,
            status="completed",
            text=text,
            character_count=len(text),
            units_processed=1,
            processed_at=datetime.now(UTC),
            warnings=["Límite de caracteres alcanzado."],
            truncated=True,
        )

    monkeypatch.setattr(h["extraction_service"], "extract", mock_extract)

    service = InstrumentExtractionService(
        projects=h["projects"],
        documents=h["documents"],
        extraction_service=h["extraction_service"],
        provider=FixtureInstrumentProvider(),
        instrument_service=h["instrument_service"],
    )

    result = service.extract(proj.id, doc.id)
    assert result.truncated is True


def test_13_fragmentation_no_patterns(tmp_path):
    """13. Fragmentación incompleta: documento sin patrones suficientes para seleccionar."""
    h = _setup_harness(tmp_path)
    proj = _seed_project(h)

    narrative = (
        "El presente informe analiza la historia de la pedagogia en el siglo XIX. "
        "Se consultaron diversas fuentes bibliograficas y cronicas coloniales."
    )
    doc = h["documents"].add(proj.id, "historia.docx", _build_docx_bytes([narrative]))

    service = InstrumentExtractionService(
        projects=h["projects"],
        documents=h["documents"],
        extraction_service=h["extraction_service"],
        provider=FixtureInstrumentProvider(),
        instrument_service=h["instrument_service"],
    )

    result = service.extract(proj.id, doc.id)
    assert result.status == "no_instruments_found"
    assert len(result.instruments) == 0
    assert any("patrones" in w for w in result.warnings)


def test_14_unknown_dimension(tmp_path):
    """14. Dimensión desconocida: candidato con dimensión no vinculada."""
    v_id = uuid4()
    cand = CandidateInstrument(
        name="Test Dimension Desconocida",
        variables=[ExtractedVariable(variable_id=v_id, name="Variable X")],
        dimensions=[],  # No dimensions defined!
        indicators=[],
        items=[
            ExtractedItem(
                variable_id=v_id,
                dimension_id=None,  # Missing dimension!
                indicator_id=None,
                text="Pregunta huérfana de dimensión.",
                response_type="single_choice",
                response_options=[
                    ExtractedResponseOption(code="1", label="A", numeric_value=1.0),
                    ExtractedResponseOption(code="2", label="B", numeric_value=2.0),
                ],
            )
        ],
        scoring_rules=[],
    )

    assert cand.is_complete is False
    assert "dimensions" in cand.pending_fields

    h = _setup_harness(tmp_path)
    service = InstrumentExtractionService(
        projects=h["projects"],
        documents=h["documents"],
        extraction_service=h["extraction_service"],
        provider=FixtureInstrumentProvider(),
        instrument_service=h["instrument_service"],
    )

    valid, reasons = service.can_convert_to_canonical(cand)
    assert valid is False
    assert any("dimension" in r.lower() for r in reasons)

    with pytest.raises(IncompleteCandidateError):
        service.create_draft_from_candidate(uuid4(), uuid4(), cand)


def test_15_response_options_without_verifiable_numbers(tmp_path):
    """15. Alternativas de respuesta sin códigos numéricos comprobables."""
    v_id = uuid4()
    d_id = uuid4()
    ind_id = uuid4()

    cand = CandidateInstrument(
        name="Escala Cualitativa",
        variables=[ExtractedVariable(variable_id=v_id, name="Var")],
        dimensions=[ExtractedDimension(dimension_id=d_id, variable_id=v_id, name="Dim")],
        indicators=[ExtractedIndicator(indicator_id=ind_id, dimension_id=d_id, name="Ind")],
        items=[
            ExtractedItem(
                variable_id=v_id,
                dimension_id=d_id,
                indicator_id=ind_id,
                text="Enunciado con escala cualitativa pura.",
                response_type="single_choice",
                response_options=[
                    # numeric_value is None because document only has categorical labels
                    ExtractedResponseOption(code="A", label="Bajo", numeric_value=None),
                    ExtractedResponseOption(code="B", label="Alto", numeric_value=None),
                ],
            )
        ],
        scoring_rules=[],
    )

    assert cand.is_complete is False
    assert any("numeric_value" in p for p in cand.pending_fields)

    h = _setup_harness(tmp_path)
    service = InstrumentExtractionService(
        projects=h["projects"],
        documents=h["documents"],
        extraction_service=h["extraction_service"],
        provider=FixtureInstrumentProvider(),
        instrument_service=h["instrument_service"],
    )

    valid, reasons = service.can_convert_to_canonical(cand)
    assert valid is False
    assert any("numérico" in r for r in reasons)


def test_16_incomplete_scoring_rule(tmp_path):
    """16. Regla de puntuación incompleta."""
    v_id = uuid4()
    d_id = uuid4()
    ind_id = uuid4()
    it_id = uuid4()

    cand = CandidateInstrument(
        name="Instrumento con Regla Rota",
        variables=[ExtractedVariable(variable_id=v_id, name="Var")],
        dimensions=[ExtractedDimension(dimension_id=d_id, variable_id=v_id, name="Dim")],
        indicators=[ExtractedIndicator(indicator_id=ind_id, dimension_id=d_id, name="Ind")],
        items=[
            ExtractedItem(
                item_id=it_id,
                variable_id=v_id,
                dimension_id=d_id,
                indicator_id=ind_id,
                text="Ítem 1",
                response_type="single_choice",
                response_options=[
                    ExtractedResponseOption(code="1", label="A", numeric_value=1.0),
                    ExtractedResponseOption(code="2", label="B", numeric_value=2.0),
                ],
            )
        ],
        scoring_rules=[
            ExtractedScoringRule(
                name="Regla Incompleta",
                scope="unknown",  # Incomplete!
                aggregation="unknown",  # Incomplete!
                item_ids=[],  # Incomplete!
            )
        ],
    )

    assert cand.is_complete is False
    assert any("scoring_rules" in p for p in cand.pending_fields)


def test_17_missing_and_ambiguous_citations(tmp_path):
    """17. Citas inexistentes o ambiguas."""
    h = _setup_harness(tmp_path)
    proj = _seed_project(h)

    text = (
        "ANEXO 1: CUESTIONARIO GENERAL\n"
        "Comentario repetido.\n"
        "1. Primer reactivo.\n"
        "Comentario repetido.\n"
    )
    doc = h["documents"].add(proj.id, "citas.docx", _build_docx_bytes([text]))

    provider_response = {
        "instruments": [
            {
                "name": "Cuestionario General",
                "variables": [
                    {
                        "name": "Var",
                        "evidence_quote": "CITA TOTALMENTE INEXISTENTE EN EL TEXTO",
                    }
                ],
                "dimensions": [
                    {
                        "name": "Dim",
                        "evidence_quote": "Comentario repetido.",  # Appears twice!
                    }
                ],
                "indicators": [],
                "items": [
                    {
                        "item_number": 1,
                        "text": "Primer reactivo.",
                        "source_quote": "Primer reactivo.",  # Literal match!
                        "response_type": "single_choice",
                        "response_options": [
                            {"code": "1", "label": "A", "numeric_value": 1.0},
                            {"code": "2", "label": "B", "numeric_value": 2.0},
                        ],
                    }
                ],
                "scoring_rules": [],
                "warnings": [],
            }
        ],
        "warnings": [],
    }

    service = InstrumentExtractionService(
        projects=h["projects"],
        documents=h["documents"],
        extraction_service=h["extraction_service"],
        provider=FixtureInstrumentProvider(default_response=provider_response),
        instrument_service=h["instrument_service"],
    )

    result = service.extract(proj.id, doc.id)

    # 1 quote is verified ("Primer reactivo.")
    # 1 quote is missing ("CITA TOTALMENTE INEXISTENTE...")
    # 1 quote is ambiguous ("Comentario repetido.")
    missing_ev = next((e for e in result.evidences if "INEXISTENTE" in e.quote), None)
    assert missing_ev is not None
    assert missing_ev.verified is False

    ambiguous_ev = next((e for e in result.evidences if "Comentario repetido" in e.quote), None)
    assert ambiguous_ev is not None
    assert ambiguous_ev.verified is False
    assert "ambigua" in (ambiguous_ev.warning or "").lower()

    valid_ev = next((e for e in result.evidences if "Primer reactivo" in e.quote), None)
    assert valid_ev is not None
    assert valid_ev.verified is True


def test_18_invalid_json_response(tmp_path):
    """18. Respuesta JSON inválida."""
    h = _setup_harness(tmp_path)
    proj = _seed_project(h)

    text = "ANEXO 1: CUESTIONARIO\n1. Pregunta.\n"
    doc = h["documents"].add(proj.id, "json_invalido.docx", _build_docx_bytes([text]))

    service = InstrumentExtractionService(
        projects=h["projects"],
        documents=h["documents"],
        extraction_service=h["extraction_service"],
        provider=FixtureInstrumentProvider(default_response="ESTO NO ES UN JSON {}{}"),
        instrument_service=h["instrument_service"],
    )

    result = service.extract(proj.id, doc.id)
    assert result.status == "failed"
    assert any("esquema estructurado" in w for w in result.warnings)


def test_19_provider_quota_and_timeout(tmp_path):
    """19. Error de cuota o timeout."""
    h = _setup_harness(tmp_path)
    proj = _seed_project(h)

    text = "ANEXO 1: CUESTIONARIO\n1. Pregunta.\n"
    doc = h["documents"].add(proj.id, "error.docx", _build_docx_bytes([text]))

    # Quota error
    service_quota = InstrumentExtractionService(
        projects=h["projects"],
        documents=h["documents"],
        extraction_service=h["extraction_service"],
        provider=FixtureInstrumentProvider(responses=[AIError("quota")]),
        instrument_service=h["instrument_service"],
    )
    res_quota = service_quota.extract(proj.id, doc.id)
    assert res_quota.status == "failed"
    assert any("quota" in w for w in res_quota.warnings)

    # Timeout error
    service_timeout = InstrumentExtractionService(
        projects=h["projects"],
        documents=h["documents"],
        extraction_service=h["extraction_service"],
        provider=FixtureInstrumentProvider(responses=[AIError("timeout")]),
        instrument_service=h["instrument_service"],
    )
    res_timeout = service_timeout.extract(proj.id, doc.id)
    assert res_timeout.status == "failed"
    assert any("timeout" in w for w in res_timeout.warnings)


def test_20_provider_not_configured(tmp_path):
    """20. Proveedor no configurado."""
    h = _setup_harness(tmp_path)
    proj = _seed_project(h)

    text = "ANEXO 1: CUESTIONARIO\n1. Pregunta.\n"
    doc = h["documents"].add(proj.id, "not_configured.docx", _build_docx_bytes([text]))

    unconfigured_provider = FixtureInstrumentProvider(configured=False)
    service = InstrumentExtractionService(
        projects=h["projects"],
        documents=h["documents"],
        extraction_service=h["extraction_service"],
        provider=unconfigured_provider,
        instrument_service=h["instrument_service"],
    )

    result = service.extract(proj.id, doc.id)
    assert result.status == "failed"
    assert any("not_configured" in w for w in result.warnings)


def test_21_external_invocation_without_consent(tmp_path):
    """21. Intento de invocación externa sin consentimiento."""
    h = _setup_harness(tmp_path)
    proj = _seed_project(h)

    text = "ANEXO 1: CUESTIONARIO PRIVADO\n1. Pregunta confidencial.\n"
    doc = h["documents"].add(proj.id, "confidencial.docx", _build_docx_bytes([text]))

    # External provider stub
    class ExternalProviderStub:
        model = "@cf/meta/llama-3.1-8b-instruct"
        configured = True
        is_external = True

        def generate(self, system, content, schema, *, max_tokens=None):
            return "{}"

    service = InstrumentExtractionService(
        projects=h["projects"],
        documents=h["documents"],
        extraction_service=h["extraction_service"],
        provider=InstrumentExtractionProvider(model=ExternalProviderStub()),  # type: ignore
        instrument_service=h["instrument_service"],
    )

    # Calling without external_ai_consent returns failed status with explicit refusal
    res = service.extract(proj.id, doc.id, external_ai_consent=False)
    assert res.status == "failed"
    assert any("autorización explícita" in w for w in res.warnings)

    # Calling with strict_consent=True raises DocumentExtractionConsentRequired
    with pytest.raises(DocumentExtractionConsentRequired):
        service.extract(proj.id, doc.id, external_ai_consent=False, strict_consent=True)


def _build_valid_instrument_entities():
    var_id = uuid4()
    dim_id = uuid4()
    ind_id = uuid4()
    it_id = uuid4()
    variables = [InstrumentVariable(variable_id=var_id, name="Desempeño")]
    dimensions = [InstrumentDimension(dimension_id=dim_id, variable_id=var_id, name="Dim")]
    indicators = [InstrumentIndicator(indicator_id=ind_id, dimension_id=dim_id, name="Ind")]
    items = [
        InstrumentItem(
            item_id=it_id,
            variable_id=var_id,
            dimension_id=dim_id,
            indicator_id=ind_id,
            text="Item 1",
            response_type="single_choice",
            response_options=[
                ResponseOption(code="1", label="A", numeric_value=1.0),
                ResponseOption(code="2", label="B", numeric_value=2.0),
            ],
        )
    ]
    return variables, dimensions, indicators, items


def test_22_check_stale_source_document_modified_or_deleted(tmp_path):
    """22. Documento fuente modificado o eliminado en check_stale."""
    h = _setup_harness(tmp_path)
    proj = _seed_project(h)

    data = _build_docx_bytes(["Cuestionario original."])
    doc = h["documents"].add(proj.id, "doc_original.docx", data)
    rev, m_var_id = _seed_reviewed_methodology(h, proj.id, doc.id)

    variables, dimensions, indicators, items = _build_valid_instrument_entities()

    # Create draft and link methodology
    inst = h["instrument_service"].create_draft(
        project_id=proj.id,
        variables=variables,
        dimensions=dimensions,
        indicators=indicators,
        items=items,
    )
    linked = h["instrument_service"].link_methodology(
        proj.id,
        inst.instrument_id,
        0,
        doc.id,
        variable_links={variables[0].variable_id: m_var_id},
    )

    # Initial check: not stale
    stale, reasons = h["instrument_service"].check_stale(proj.id, linked.instrument_id)
    assert stale is False
    assert len(reasons) == 0

    # Modify source document bytes in storage
    h["doc_repo"]._path(doc.id).write_bytes(b"Contenido modificado que altera el hash!")
    stale_mod, reasons_mod = h["instrument_service"].check_stale(proj.id, linked.instrument_id)
    assert stale_mod is True
    assert any("modificado" in r for r in reasons_mod)

    # Delete source document
    h["doc_repo"].delete(proj.id, doc.id)
    stale_del, reasons_del = h["instrument_service"].check_stale(proj.id, linked.instrument_id)
    assert stale_del is True
    assert any("eliminado" in r for r in reasons_del)


def test_23_check_stale_outdated_methodology_review(tmp_path):
    """23. Revisión metodológica desactualizada en check_stale."""
    h = _setup_harness(tmp_path)
    proj = _seed_project(h)

    data = _build_docx_bytes(["Cuestionario."])
    doc = h["documents"].add(proj.id, "doc.docx", data)
    rev, m_var_id = _seed_reviewed_methodology(h, proj.id, doc.id)

    variables, dimensions, indicators, items = _build_valid_instrument_entities()

    inst = h["instrument_service"].create_draft(
        project_id=proj.id,
        variables=variables,
        dimensions=dimensions,
        indicators=indicators,
        items=items,
    )
    linked = h["instrument_service"].link_methodology(
        proj.id,
        inst.instrument_id,
        0,
        doc.id,
        variable_links={variables[0].variable_id: m_var_id},
    )

    # Update review version and content
    new_content = rev.content.model_copy(
        update={"title": ReviewFinding(value="Nuevo Titulo Modificado", kind="manual")}
    )
    new_rev = rev.model_copy(update={"version": 2, "content": new_content})
    saved = h["methodology_repo"].save_review(new_rev, expected_version=1)
    assert saved is True

    stale, reasons = h["instrument_service"].check_stale(proj.id, linked.instrument_id)
    assert stale is True
    assert any("metodología ha cambiado" in r.lower() for r in reasons)


def test_24_legacy_link_methodology_calls(tmp_path):
    """24. Llamadas heredadas a link_methodology(): compatibilidad hacia atrás."""
    h = _setup_harness(tmp_path)
    proj = _seed_project(h)

    data = _build_docx_bytes(["Documento unico."])
    doc = h["documents"].add(proj.id, "monografia.docx", data)
    rev, m_var_id = _seed_reviewed_methodology(h, proj.id, doc.id)

    variables, dimensions, indicators, items = _build_valid_instrument_entities()

    inst = h["instrument_service"].create_draft(
        project_id=proj.id,
        variables=variables,
        dimensions=dimensions,
        indicators=indicators,
        items=items,
    )

    # Legacy signature: only project_id, instrument_id, expected_version, document_id
    linked = h["instrument_service"].link_methodology(
        proj.id,
        inst.instrument_id,
        0,
        doc.id,
        variable_links={variables[0].variable_id: m_var_id},
    )

    assert linked.provenance is not None
    assert linked.provenance.source_document_id == doc.id
    assert linked.provenance.methodology_review_id == doc.id
    assert linked.provenance.source_document_hash == _sha256(data)
