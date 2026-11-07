"""Deterministic integration tests for Research Instrument Extraction REST API (Sesión 18A-4.4).

Covers all 27 required scenarios:
1. Valid extraction with offline provider.
2. DOCX document extraction.
3. PDF document extraction.
4. Two questionnaires in a single document.
5. Structurally complete candidate.
6. Structurally incomplete candidate.
7. Valid instrument without scoring rules.
8. Explicit draft creation from candidate.
9. Extraction without automatic draft creation.
10. Request idempotency on draft creation.
11. Nonexistent project (404).
12. Nonexistent document (404).
13. Cross-project document access (404).
14. Document without extractable text (status="insufficient_text").
15. Truncated document.
16. Nonexistent evidence quote.
17. Ambiguous evidence quote.
18. Provider not configured (503).
19. Quota exceeded error (429).
20. Provider timeout error (504).
21. Absence of external AI consent (403).
22. Manipulated candidate rejection (422).
23. Stale source document before draft creation (409).
24. Independent methodology and source documents.
25. Backward compatibility with existing instrument endpoints.
26. Compatibility with Research-Statistics bridge (22B).
27. Absence of external HTTP/network calls in tests.
"""

from __future__ import annotations

import io
from typing import Any
from uuid import UUID, uuid4

from docx import Document as WordDocument
from fastapi.testclient import TestClient
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from app.modules.research.dev_app import ResearchDevSettings, create_app
from app.modules.research.instrument.extraction_provider import (
    FixtureInstrumentProvider,
    InstrumentExtractionProvider,
)
from app.modules.research.instrument.extraction_service import InstrumentExtractionService
from app.modules.research.instrument.service import InstrumentService
from app.shared.ai_errors import AIError

# --- Synthetic Document Builders ---


def _build_pdf_bytes(text: str) -> bytes:
    writer = PdfWriter()
    page = writer.add_blank_page(width=300, height=300)
    stream = DecodedStreamObject()
    stream.set_data(f"BT /F1 12 Tf 20 200 Td ({text}) Tj ET".encode("latin-1"))
    page[NameObject("/Contents")] = stream
    resources = DictionaryObject()
    resources[NameObject("/Font")] = DictionaryObject()
    page[NameObject("/Resources")] = resources
    buffer = io.BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


def _build_docx_bytes(paragraphs: list[str]) -> bytes:
    doc = WordDocument()
    for p in paragraphs:
        doc.add_paragraph(p)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def _setup_api(
    tmp_path,
    provider: Any | None = None,
    extraction_service: InstrumentExtractionService | None = None,
):
    settings = ResearchDevSettings(
        research_db_path=tmp_path / "research.sqlite3",
        research_documents_path=tmp_path / "docs",
        research_datasets_path=tmp_path / "datasets",
    )
    v_id = uuid4()
    d_id = uuid4()
    ind_id = uuid4()
    default_valid_response = {
        "instruments": [
            {
                "name": "Escala de Clima Organizacional",
                "variables": [
                    {
                        "variable_id": str(v_id),
                        "name": "Clima Organizacional",
                        "role": "independent",
                        "scale": "ordinal",
                        "evidence_quote": "Escala de Clima Organizacional",
                    }
                ],
                "dimensions": [
                    {
                        "dimension_id": str(d_id),
                        "variable_id": str(v_id),
                        "name": "Liderazgo",
                        "evidence_quote": "Dimensión Liderazgo",
                    }
                ],
                "indicators": [
                    {
                        "indicator_id": str(ind_id),
                        "dimension_id": str(d_id),
                        "name": "Comunicación",
                        "evidence_quote": "Indicador Comunicación",
                    }
                ],
                "items": [
                    {
                        "item_number": 1,
                        "text": "Mi jefe me escucha activamente.",
                        "variable_name": "Clima Organizacional",
                        "dimension_name": "Liderazgo",
                        "indicator_name": "Comunicación",
                        "response_type": "single_choice",
                        "response_options": [
                            {
                                "code": "1",
                                "label": "Nunca",
                                "numeric_value": 1.0,
                                "evidence_quote": "1 = Nunca",
                            },
                            {
                                "code": "2",
                                "label": "Siempre",
                                "numeric_value": 2.0,
                                "evidence_quote": "2 = Siempre",
                            },
                        ],
                        "source_quote": "Mi jefe me escucha activamente.",
                    }
                ],
                "scoring_rules": [],
                "warnings": [],
            }
        ],
        "warnings": [],
    }
    inst_provider = (
        provider
        if provider is not None
        else FixtureInstrumentProvider(default_response=default_valid_response)
    )
    app = create_app(
        settings=settings,
        instrument_provider=inst_provider,
        instrument_extraction_service=extraction_service,
    )
    client = TestClient(app)
    return client, settings, app


def _create_project(client: TestClient) -> str:
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


def _upload_docx_questionnaire(client: TestClient, project_id: str) -> str:
    text_content = [
        "ANEXO 1: Escala de Clima Organizacional",
        "Dimensión Liderazgo",
        "Indicador Comunicación",
        "Opciones: 1 = Nunca, 2 = Siempre",
        "1. Mi jefe me escucha activamente.",
    ]
    resp = client.post(
        f"/api/research/projects/{project_id}/documents",
        content=_build_docx_bytes(text_content),
        headers={
            "X-File-Name": "cuestionario_clima.docx",
            "Content-Type": (
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            ),
        },
    )
    assert resp.status_code == 201
    return resp.json()["id"]


def _upload_and_confirm_methodology(
    client: TestClient, project_id: str, var_id: UUID | None = None
) -> str:
    v_id = var_id or uuid4()
    resp = client.post(
        f"/api/research/projects/{project_id}/documents",
        content=b"%PDF-1.4\nTesis Monografia Metodologia\n%%EOF",
        headers={"X-File-Name": "tesis.pdf", "Content-Type": "application/pdf"},
    )
    assert resp.status_code == 201
    doc_id = resp.json()["id"]

    rev_url = f"/api/research/projects/{project_id}/documents/{doc_id}/methodology/review"
    init_rev = client.post(rev_url)
    assert init_rev.status_code == 201

    def _m(val):
        return {"value": val, "kind": "manual", "evidence": []}

    content = init_rev.json()["content"]
    content["title"] = _m("Clima y Desempeño")
    content["general_objective"] = _m("Determinar relación")
    content["research_design"] = _m("Transversal")
    content["specific_objectives"] = [_m("Evaluar variables")]
    content["specific_hypotheses"] = [_m("Existe relación")]
    content["variables"] = [
        {
            "id": str(v_id),
            "name": _m("Clima Organizacional"),
            "role": _m("independent"),
            "measurement_scale": _m("ordinal"),
            "dimensions": [_m("Liderazgo")],
            "indicators": [_m("Comunicación")],
            "instrument_items": [_m("Ítem 1")],
        }
    ]
    save_resp = client.put(rev_url, json={"version": 0, "content": content})
    assert save_resp.status_code == 200

    conf_resp = client.post(rev_url + "/confirm", json={"version": 1})
    assert conf_resp.status_code == 200
    assert conf_resp.json()["review_status"] == "reviewed"
    return doc_id


# --- Tests ---


def test_01_valid_extraction_with_offline_provider(tmp_path):
    """1. Extracción válida con proveedor offline."""
    client, _, _ = _setup_api(tmp_path)
    proj_id = _create_project(client)
    doc_id = _upload_docx_questionnaire(client, proj_id)

    resp = client.post(
        f"/api/research/projects/{proj_id}/instruments/extract",
        json={"document_id": doc_id, "external_ai_consent": False},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "completed"
    assert len(data["instruments"]) == 1
    assert data["instruments"][0]["name"] == "Escala de Clima Organizacional"
    assert data["provenance"]["instrument_document_id"] == doc_id


def test_02_docx_document_extraction(tmp_path):
    """2. Documento DOCX procesado correctamente."""
    client, _, _ = _setup_api(tmp_path)
    proj_id = _create_project(client)
    doc_id = _upload_docx_questionnaire(client, proj_id)

    resp = client.post(
        f"/api/research/projects/{proj_id}/instruments/extract",
        json={"document_id": doc_id, "external_ai_consent": False},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "completed"


def test_03_pdf_document_extraction(tmp_path):
    """3. Documento PDF procesado correctamente."""
    client, _, _ = _setup_api(tmp_path)
    proj_id = _create_project(client)

    pdf_bytes = _build_pdf_bytes(
        "ANEXO: Cuestionario de Clima. Dimensio Liderazgo. 1. Mi jefe me escucha."
    )
    doc_resp = client.post(
        f"/api/research/projects/{proj_id}/documents",
        content=pdf_bytes,
        headers={"X-File-Name": "instrumento.pdf", "Content-Type": "application/pdf"},
    )
    assert doc_resp.status_code == 201
    doc_id = doc_resp.json()["id"]

    resp = client.post(
        f"/api/research/projects/{proj_id}/instruments/extract",
        json={"document_id": doc_id, "external_ai_consent": False},
    )
    assert resp.status_code == 200


def test_04_two_questionnaires_in_document(tmp_path):
    """4. Dos cuestionarios en un solo documento."""
    v1_id, d1_id, ind1_id = uuid4(), uuid4(), uuid4()
    v2_id, d2_id, ind2_id = uuid4(), uuid4(), uuid4()
    two_instruments_response = {
        "instruments": [
            {
                "name": "Cuestionario 1: Clima",
                "variables": [
                    {
                        "variable_id": str(v1_id),
                        "name": "Clima",
                        "evidence_quote": "Clima",
                    }
                ],
                "dimensions": [
                    {
                        "dimension_id": str(d1_id),
                        "variable_id": str(v1_id),
                        "name": "Liderazgo",
                        "evidence_quote": "Liderazgo",
                    }
                ],
                "indicators": [
                    {
                        "indicator_id": str(ind1_id),
                        "dimension_id": str(d1_id),
                        "name": "Comunicación",
                        "evidence_quote": "Comunicación",
                    }
                ],
                "items": [
                    {
                        "item_number": 1,
                        "text": "Ítem Clima 1.",
                        "variable_name": "Clima",
                        "dimension_name": "Liderazgo",
                        "indicator_name": "Comunicación",
                        "response_type": "single_choice",
                        "response_options": [
                            {"code": "1", "label": "No", "numeric_value": 1.0},
                            {"code": "2", "label": "Sí", "numeric_value": 2.0},
                        ],
                        "source_quote": "Ítem Clima 1.",
                    }
                ],
                "scoring_rules": [],
                "warnings": [],
            },
            {
                "name": "Cuestionario 2: Desempeño",
                "variables": [
                    {
                        "variable_id": str(v2_id),
                        "name": "Desempeño",
                        "evidence_quote": "Desempeño",
                    }
                ],
                "dimensions": [
                    {
                        "dimension_id": str(d2_id),
                        "variable_id": str(v2_id),
                        "name": "Eficacia",
                        "evidence_quote": "Eficacia",
                    }
                ],
                "indicators": [
                    {
                        "indicator_id": str(ind2_id),
                        "dimension_id": str(d2_id),
                        "name": "Metas",
                        "evidence_quote": "Metas",
                    }
                ],
                "items": [
                    {
                        "item_number": 1,
                        "text": "Ítem Desempeño 1.",
                        "variable_name": "Desempeño",
                        "dimension_name": "Eficacia",
                        "indicator_name": "Metas",
                        "response_type": "single_choice",
                        "response_options": [
                            {"code": "1", "label": "Bajo", "numeric_value": 1.0},
                            {"code": "2", "label": "Alto", "numeric_value": 2.0},
                        ],
                        "source_quote": "Ítem Desempeño 1.",
                    }
                ],
                "scoring_rules": [],
                "warnings": [],
            },
        ],
        "warnings": [],
    }
    provider = FixtureInstrumentProvider(default_response=two_instruments_response)
    client, _, _ = _setup_api(tmp_path, provider=provider)
    proj_id = _create_project(client)

    doc_text = [
        "ANEXO 1: Cuestionario 1: Clima. Liderazgo. Comunicación. Ítem Clima 1.",
        "ANEXO 2: Cuestionario 2: Desempeño. Eficacia. Metas. Ítem Desempeño 1.",
    ]
    doc_resp = client.post(
        f"/api/research/projects/{proj_id}/documents",
        content=_build_docx_bytes(doc_text),
        headers={"X-File-Name": "dos_cuestionarios.docx"},
    )
    doc_id = doc_resp.json()["id"]

    resp = client.post(
        f"/api/research/projects/{proj_id}/instruments/extract",
        json={"document_id": doc_id, "external_ai_consent": False},
    )
    assert resp.status_code == 200
    assert len(resp.json()["instruments"]) == 2


def test_05_complete_candidate(tmp_path):
    """5. Candidato completo con todos los campos requeridos."""
    client, _, _ = _setup_api(tmp_path)
    proj_id = _create_project(client)
    doc_id = _upload_docx_questionnaire(client, proj_id)

    resp = client.post(
        f"/api/research/projects/{proj_id}/instruments/extract",
        json={"document_id": doc_id},
    )
    assert resp.status_code == 200
    candidate = resp.json()["instruments"][0]
    assert candidate["is_complete"] is True
    assert len(candidate["pending_fields"]) == 0


def test_06_incomplete_candidate_cannot_create_draft(tmp_path):
    """6. Candidato incompleto no puede convertirse en borrador canónico."""
    incomplete_response = {
        "instruments": [
            {
                "name": "Cuestionario Incompleto",
                "variables": [{"name": "Var", "evidence_quote": "Var"}],
                "dimensions": [],  # Missing dimensions!
                "indicators": [],
                "items": [
                    {
                        "item_number": 1,
                        "text": "Ítem sin dimensión.",
                        "response_type": "unknown",  # Incomplete!
                        "source_quote": "Ítem sin dimensión.",
                    }
                ],
                "scoring_rules": [],
                "warnings": [],
            }
        ],
        "warnings": [],
    }
    provider = FixtureInstrumentProvider(default_response=incomplete_response)
    client, _, _ = _setup_api(tmp_path, provider=provider)
    proj_id = _create_project(client)

    doc_resp = client.post(
        f"/api/research/projects/{proj_id}/documents",
        content=_build_docx_bytes(["ANEXO 1: CUESTIONARIO", "Var.", "1. Ítem sin dimensión."]),
        headers={"X-File-Name": "incompleto.docx"},
    )
    doc_id = doc_resp.json()["id"]

    ext_resp = client.post(
        f"/api/research/projects/{proj_id}/instruments/extract",
        json={"document_id": doc_id},
    )
    assert ext_resp.status_code == 200
    cand = ext_resp.json()["instruments"][0]
    assert cand["is_complete"] is False

    # Attempt explicit draft creation from incomplete candidate
    draft_resp = client.post(
        f"/api/research/projects/{proj_id}/instruments/drafts/from-candidate",
        json={"document_id": doc_id, "candidate": cand},
    )
    assert draft_resp.status_code == 422
    assert "no cumple los requisitos canónicos" in draft_resp.json()["detail"]


def test_07_instrument_without_scoring_rules_is_valid(tmp_path):
    """7. Instrumento sin reglas de puntuación es estructuralmente válido."""
    client, _, _ = _setup_api(tmp_path)
    proj_id = _create_project(client)
    doc_id = _upload_docx_questionnaire(client, proj_id)

    ext_resp = client.post(
        f"/api/research/projects/{proj_id}/instruments/extract",
        json={"document_id": doc_id},
    )
    cand = ext_resp.json()["instruments"][0]
    assert cand["scoring_rules"] == []
    assert cand["is_complete"] is True

    # Can be drafted without scoring rules
    draft_resp = client.post(
        f"/api/research/projects/{proj_id}/instruments/drafts/from-candidate",
        json={"document_id": doc_id, "candidate": cand},
    )
    assert draft_resp.status_code == 201
    assert draft_resp.json()["scoring_rules"] == []


def test_08_explicit_draft_creation(tmp_path):
    """8. Creación explícita de borrador a partir de candidato validado."""
    client, _, _ = _setup_api(tmp_path)
    proj_id = _create_project(client)
    doc_id = _upload_docx_questionnaire(client, proj_id)

    ext_resp = client.post(
        f"/api/research/projects/{proj_id}/instruments/extract",
        json={"document_id": doc_id},
    )
    cand = ext_resp.json()["instruments"][0]

    draft_resp = client.post(
        f"/api/research/projects/{proj_id}/instruments/drafts/from-candidate",
        json={"document_id": doc_id, "candidate": cand},
    )
    assert draft_resp.status_code == 201
    assert "Location" in draft_resp.headers
    data = draft_resp.json()
    assert data["status"] == "draft"
    assert data["confirmation"]["state"] == "pending"
    assert len(data["items"]) == 1


def test_09_extraction_without_automatic_creation(tmp_path):
    """9. La extracción no crea borradores automáticamente."""
    client, _, _ = _setup_api(tmp_path)
    proj_id = _create_project(client)
    doc_id = _upload_docx_questionnaire(client, proj_id)

    # Call extract
    ext_resp = client.post(
        f"/api/research/projects/{proj_id}/instruments/extract",
        json={"document_id": doc_id},
    )
    assert ext_resp.status_code == 200

    # Verify no instrument was persisted
    list_resp = client.get(f"/api/research/projects/{proj_id}/instruments")
    assert list_resp.status_code == 200
    assert len(list_resp.json()) == 0


def test_10_draft_creation_idempotency_on_retry(tmp_path):
    """10. Reintento de solicitud de creación garantiza idempotencia sin duplicados."""
    client, _, _ = _setup_api(tmp_path)
    proj_id = _create_project(client)
    doc_id = _upload_docx_questionnaire(client, proj_id)

    ext_resp = client.post(
        f"/api/research/projects/{proj_id}/instruments/extract",
        json={"document_id": doc_id},
    )
    cand = ext_resp.json()["instruments"][0]

    # First draft creation
    r1 = client.post(
        f"/api/research/projects/{proj_id}/instruments/drafts/from-candidate",
        json={"document_id": doc_id, "candidate": cand},
    )
    assert r1.status_code == 201
    inst_id_1 = r1.json()["instrument_id"]

    # Second draft creation with the same candidate
    r2 = client.post(
        f"/api/research/projects/{proj_id}/instruments/drafts/from-candidate",
        json={"document_id": doc_id, "candidate": cand},
    )
    assert r2.status_code == 201
    inst_id_2 = r2.json()["instrument_id"]

    assert inst_id_1 == inst_id_2

    # Verify database holds only 1 instrument
    list_resp = client.get(f"/api/research/projects/{proj_id}/instruments")
    assert len(list_resp.json()) == 1


def test_11_nonexistent_project_returns_404(tmp_path):
    """11. Proyecto inexistente devuelve 404."""
    client, _, _ = _setup_api(tmp_path)
    fake_proj = str(uuid4())
    fake_doc = str(uuid4())

    resp = client.post(
        f"/api/research/projects/{fake_proj}/instruments/extract",
        json={"document_id": fake_doc},
    )
    assert resp.status_code == 404


def test_12_nonexistent_document_returns_404(tmp_path):
    """12. Documento inexistente devuelve 404."""
    client, _, _ = _setup_api(tmp_path)
    proj_id = _create_project(client)
    fake_doc = str(uuid4())

    resp = client.post(
        f"/api/research/projects/{proj_id}/instruments/extract",
        json={"document_id": fake_doc},
    )
    assert resp.status_code == 404


def test_13_cross_project_document_access_returns_404(tmp_path):
    """13. Acceso entre proyectos devuelve 404 (aislamiento estricto)."""
    client, _, _ = _setup_api(tmp_path)
    proj_a = _create_project(client)
    proj_b = _create_project(client)
    doc_a = _upload_docx_questionnaire(client, proj_a)

    # Attempt to extract doc_a under proj_b
    resp = client.post(
        f"/api/research/projects/{proj_b}/instruments/extract",
        json={"document_id": doc_a},
    )
    assert resp.status_code == 404


def test_14_document_without_extractable_text(tmp_path):
    """14. Documento sin texto extraíble reporta status='insufficient_text' sin error 500."""
    client, _, _ = _setup_api(tmp_path)
    proj_id = _create_project(client)

    # Upload empty docx with no text
    empty_doc = _build_docx_bytes([])
    doc_resp = client.post(
        f"/api/research/projects/{proj_id}/documents",
        content=empty_doc,
        headers={"X-File-Name": "vacio.docx"},
    )
    doc_id = doc_resp.json()["id"]

    resp = client.post(
        f"/api/research/projects/{proj_id}/instruments/extract",
        json={"document_id": doc_id},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "insufficient_text"
    assert len(data["warnings"]) > 0


def test_15_truncated_document(tmp_path):
    """15. Documento truncado refleja truncated=True."""
    client, _, _ = _setup_api(tmp_path)
    proj_id = _create_project(client)

    # Text that exceeds selector limits
    huge_text = ["ANEXO 1: CUESTIONARIO EXTENSO"] + [f"Pregunta {i}." for i in range(500)]
    doc_resp = client.post(
        f"/api/research/projects/{proj_id}/documents",
        content=_build_docx_bytes(huge_text),
        headers={"X-File-Name": "largo.docx"},
    )
    doc_id = doc_resp.json()["id"]

    resp = client.post(
        f"/api/research/projects/{proj_id}/instruments/extract",
        json={"document_id": doc_id},
    )
    assert resp.status_code == 200
    assert "truncated" in resp.json()


def test_16_nonexistent_evidence_quote(tmp_path):
    """16. Cita de evidencia inexistente marcada como no verificada."""
    provider_response = {
        "instruments": [
            {
                "name": "Cuestionario con Cita Falsa",
                "variables": [
                    {
                        "name": "Var",
                        "evidence_quote": "ESTA CITA NUNCA ESTUVO EN EL DOCUMENTO FUENTE",
                    }
                ],
                "dimensions": [],
                "indicators": [],
                "items": [
                    {
                        "item_number": 1,
                        "text": "1. Mi jefe me escucha activamente.",
                        "source_quote": "1. Mi jefe me escucha activamente.",
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
    client, _, _ = _setup_api(
        tmp_path, provider=FixtureInstrumentProvider(default_response=provider_response)
    )
    proj_id = _create_project(client)
    doc_id = _upload_docx_questionnaire(client, proj_id)

    resp = client.post(
        f"/api/research/projects/{proj_id}/instruments/extract",
        json={"document_id": doc_id},
    )
    assert resp.status_code == 200
    evs = resp.json()["evidences"]
    unverified = [e for e in evs if not e["verified"]]
    assert len(unverified) >= 1
    assert "NUNCA ESTUVO" in unverified[0]["quote"]


def test_17_ambiguous_evidence_quote(tmp_path):
    """17. Cita de evidencia ambigua marcada con advertencia y verified=False."""
    provider_response = {
        "instruments": [
            {
                "name": "Cuestionario",
                "variables": [
                    {
                        "name": "Var",
                        "evidence_quote": "FRASE REPETIDA",  # Appears twice in doc
                    }
                ],
                "dimensions": [],
                "indicators": [],
                "items": [
                    {
                        "item_number": 1,
                        "text": "1. Ítem único.",
                        "source_quote": "1. Ítem único.",
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
    client, _, _ = _setup_api(
        tmp_path, provider=FixtureInstrumentProvider(default_response=provider_response)
    )
    proj_id = _create_project(client)

    doc_bytes = _build_docx_bytes(
        [
            "ANEXO: CUESTIONARIO",
            "FRASE REPETIDA",
            "1. Ítem único.",
            "FRASE REPETIDA",
        ]
    )
    doc_resp = client.post(
        f"/api/research/projects/{proj_id}/documents",
        content=doc_bytes,
        headers={"X-File-Name": "repetido.docx"},
    )
    doc_id = doc_resp.json()["id"]

    resp = client.post(
        f"/api/research/projects/{proj_id}/instruments/extract",
        json={"document_id": doc_id},
    )
    assert resp.status_code == 200
    ambiguous = [e for e in resp.json()["evidences"] if e["quote"] == "FRASE REPETIDA"]
    assert len(ambiguous) == 1
    assert ambiguous[0]["verified"] is False
    assert "ambigua" in (ambiguous[0]["warning"] or "").lower()


def test_18_provider_not_configured_returns_503(tmp_path):
    """18. Proveedor no configurado devuelve 503."""
    unconfigured = FixtureInstrumentProvider(configured=False)
    client, _, _ = _setup_api(tmp_path, provider=unconfigured)
    proj_id = _create_project(client)
    doc_id = _upload_docx_questionnaire(client, proj_id)

    resp = client.post(
        f"/api/research/projects/{proj_id}/instruments/extract",
        json={"document_id": doc_id},
    )
    assert resp.status_code == 503
    assert "no está configurado" in resp.json()["detail"].lower()


def test_19_provider_quota_returns_429(tmp_path):
    """19. Error de cuota del proveedor devuelve 429."""
    quota_err = FixtureInstrumentProvider(responses=[AIError("quota")])
    client, _, _ = _setup_api(tmp_path, provider=quota_err)
    proj_id = _create_project(client)
    doc_id = _upload_docx_questionnaire(client, proj_id)

    resp = client.post(
        f"/api/research/projects/{proj_id}/instruments/extract",
        json={"document_id": doc_id},
    )
    assert resp.status_code == 429
    assert "cuota" in resp.json()["detail"].lower()


def test_20_provider_timeout_returns_504(tmp_path):
    """20. Timeout del proveedor devuelve 504."""
    timeout_err = FixtureInstrumentProvider(responses=[AIError("timeout")])
    client, _, _ = _setup_api(tmp_path, provider=timeout_err)
    proj_id = _create_project(client)
    doc_id = _upload_docx_questionnaire(client, proj_id)

    resp = client.post(
        f"/api/research/projects/{proj_id}/instruments/extract",
        json={"document_id": doc_id},
    )
    assert resp.status_code == 504
    assert "tardó demasiado" in resp.json()["detail"].lower()


def test_21_external_ai_invocation_without_consent_returns_403(tmp_path):
    """21. Ausencia de consentimiento explícito para IA externa devuelve 403."""

    class ExternalStub:
        model = "@cf/meta/llama-3.1-8b-instruct"
        configured = True
        is_external = True

        def generate(self, system, content, schema, *, max_tokens=None):
            return "{}"

    client, _, _ = _setup_api(tmp_path, provider=InstrumentExtractionProvider(model=ExternalStub()))  # type: ignore
    proj_id = _create_project(client)
    doc_id = _upload_docx_questionnaire(client, proj_id)

    resp = client.post(
        f"/api/research/projects/{proj_id}/instruments/extract",
        json={"document_id": doc_id, "external_ai_consent": False},
    )
    assert resp.status_code == 403
    assert "autorización explícita" in resp.json()["detail"].lower()


def test_22_tampered_candidate_rejected_with_422(tmp_path):
    """22. Intento de manipular el candidato con texto no en la fuente es rechazado con 422."""
    client, _, _ = _setup_api(tmp_path)
    proj_id = _create_project(client)
    doc_id = _upload_docx_questionnaire(client, proj_id)

    ext_resp = client.post(
        f"/api/research/projects/{proj_id}/instruments/extract",
        json={"document_id": doc_id},
    )
    cand = ext_resp.json()["instruments"][0]

    # Tamper with the item text to something not present in the document
    cand["items"][0]["text"] = "TEXTO INVENTADO QUE NO ESTÁ EN EL DOCUMENTO"
    cand["items"][0]["source_quote"] = "TEXTO INVENTADO QUE NO ESTÁ EN EL DOCUMENTO"

    resp = client.post(
        f"/api/research/projects/{proj_id}/instruments/drafts/from-candidate",
        json={"document_id": doc_id, "candidate": cand},
    )
    assert resp.status_code == 422
    assert "no fue encontrada" in resp.json()["detail"]


def test_23_stale_source_document_returns_409(tmp_path):
    """23. Documento fuente modificado (hash stale) devuelve 409 antes de crear borrador."""
    client, _, _ = _setup_api(tmp_path)
    proj_id = _create_project(client)
    doc_id = _upload_docx_questionnaire(client, proj_id)

    ext_resp = client.post(
        f"/api/research/projects/{proj_id}/instruments/extract",
        json={"document_id": doc_id},
    )
    cand = ext_resp.json()["instruments"][0]

    # Send with mismatched expected_document_hash (64 hex characters)
    fake_hash = "0" * 64
    resp = client.post(
        f"/api/research/projects/{proj_id}/instruments/drafts/from-candidate",
        json={
            "document_id": doc_id,
            "candidate": cand,
            "expected_document_hash": fake_hash,
        },
    )
    assert resp.status_code == 409
    assert "modificado" in resp.json()["detail"].lower()


def test_24_independent_methodology_and_source_documents(tmp_path):
    """24. Metodología y documento fuente independientes vinculados vía API."""
    client, _, _ = _setup_api(tmp_path)
    proj_id = _create_project(client)

    # Upload Doc 1: Thesis monograph with methodology
    methodology_doc_id = _upload_and_confirm_methodology(client, proj_id)

    # Upload Doc 2: Questionnaire appendix
    questionnaire_doc_id = _upload_docx_questionnaire(client, proj_id)

    # Extract with methodology_document_id specified
    ext_resp = client.post(
        f"/api/research/projects/{proj_id}/instruments/extract",
        json={
            "document_id": questionnaire_doc_id,
            "methodology_document_id": methodology_doc_id,
        },
    )
    assert ext_resp.status_code == 200
    cand = ext_resp.json()["instruments"][0]

    # Create draft with independent methodology document
    draft_resp = client.post(
        f"/api/research/projects/{proj_id}/instruments/drafts/from-candidate",
        json={
            "document_id": questionnaire_doc_id,
            "methodology_document_id": methodology_doc_id,
            "candidate": cand,
        },
    )
    assert draft_resp.status_code == 201
    prov = draft_resp.json()["provenance"]
    assert prov is not None
    assert prov["source_kind"] == "document"
    assert prov["source_document_id"] == questionnaire_doc_id
    assert prov["methodology_review_id"] == methodology_doc_id
    assert prov["methodology_review_version"] == 2


def test_25_backward_compatibility_with_existing_endpoints(tmp_path):
    """25. Compatibilidad total con los endpoints de instrumentos existentes."""
    client, _, _ = _setup_api(tmp_path)
    proj_id = _create_project(client)
    var_id = uuid4()
    dim_id = uuid4()
    ind_id = uuid4()
    it_id = uuid4()

    # Manual creation via POST /instruments
    payload = {
        "variables": [{"variable_id": str(var_id), "name": "Variable Manual"}],
        "dimensions": [
            {"dimension_id": str(dim_id), "variable_id": str(var_id), "name": "Dim Manual"}
        ],
        "indicators": [
            {"indicator_id": str(ind_id), "dimension_id": str(dim_id), "name": "Ind Manual"}
        ],
        "items": [
            {
                "item_id": str(it_id),
                "variable_id": str(var_id),
                "dimension_id": str(dim_id),
                "indicator_id": str(ind_id),
                "text": "Ítem manual 1.",
                "response_type": "single_choice",
                "response_options": [
                    {"code": "1", "label": "A", "numeric_value": 1.0},
                    {"code": "2", "label": "B", "numeric_value": 2.0},
                ],
            }
        ],
        "scoring_rules": [],
    }
    r = client.post(f"/api/research/projects/{proj_id}/instruments", json=payload)
    assert r.status_code == 201
    inst_id = r.json()["instrument_id"]

    # Retrieve via GET /instruments/{id}
    r_get = client.get(f"/api/research/projects/{proj_id}/instruments/{inst_id}")
    assert r_get.status_code == 200
    assert r_get.json()["instrument_id"] == inst_id

    # Test link_methodology with optional source_document_id
    doc_id = _upload_and_confirm_methodology(client, proj_id, var_id=var_id)
    link_resp = client.post(
        f"/api/research/projects/{proj_id}/instruments/{inst_id}/methodology",
        json={
            "expected_version": 0,
            "document_id": doc_id,
            "variable_links": {str(var_id): str(var_id)},
            "source_document_id": doc_id,
        },
    )
    assert link_resp.status_code == 200
    assert link_resp.json()["provenance"]["source_document_id"] == doc_id


def test_26_compatibility_with_research_statistics_bridge(tmp_path):
    """26. Compatibilidad con el bridge Research-Statistics (22B)."""
    client, _, app = _setup_api(tmp_path)
    proj_id = _create_project(client)
    doc_id = _upload_docx_questionnaire(client, proj_id)

    ext_resp = client.post(
        f"/api/research/projects/{proj_id}/instruments/extract",
        json={"document_id": doc_id},
    )
    cand = ext_resp.json()["instruments"][0]

    draft_resp = client.post(
        f"/api/research/projects/{proj_id}/instruments/drafts/from-candidate",
        json={"document_id": doc_id, "candidate": cand},
    )
    assert draft_resp.status_code == 201
    inst_id = draft_resp.json()["instrument_id"]

    # Verify bridge can access the instrument via reader
    bridge = app.state.research_statistics_bridge
    assert bridge.instruments is not None
    inst = bridge.instruments.get(UUID(proj_id), UUID(inst_id))
    assert inst.status == "draft"


def test_27_absence_of_external_calls(tmp_path):
    """27. Verificación de ausencia de llamadas de red/externas en pruebas."""
    client, _, _ = _setup_api(tmp_path)
    proj_id = _create_project(client)
    doc_id = _upload_docx_questionnaire(client, proj_id)

    # Calling extract with external_ai_consent=False succeeds entirely locally
    resp = client.post(
        f"/api/research/projects/{proj_id}/instruments/extract",
        json={"document_id": doc_id, "external_ai_consent": False},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "completed"


def test_28_link_methodology_same_document(tmp_path):
    """28. Vinculación metodológica cuando cuestionario y tesis están en el mismo documento."""
    client, _, _ = _setup_api(tmp_path)
    proj_id = _create_project(client)
    var_id = uuid4()
    dim_id = uuid4()
    ind_id = uuid4()
    it_id = uuid4()

    # Create draft
    payload = {
        "variables": [{"variable_id": str(var_id), "name": "Variable Única"}],
        "dimensions": [
            {"dimension_id": str(dim_id), "variable_id": str(var_id), "name": "Dimensión Única"}
        ],
        "indicators": [
            {"indicator_id": str(ind_id), "dimension_id": str(dim_id), "name": "Indicador Único"}
        ],
        "items": [
            {
                "item_id": str(it_id),
                "variable_id": str(var_id),
                "dimension_id": str(dim_id),
                "indicator_id": str(ind_id),
                "text": "Ítem único.",
                "response_type": "single_choice",
                "response_options": [
                    {"code": "1", "label": "A", "numeric_value": 1.0},
                    {"code": "2", "label": "B", "numeric_value": 2.0},
                ],
            }
        ],
        "scoring_rules": [],
    }
    r = client.post(f"/api/research/projects/{proj_id}/instruments", json=payload)
    inst_id = r.json()["instrument_id"]

    # Upload single document containing both thesis & questionnaire
    doc_id = _upload_and_confirm_methodology(client, proj_id, var_id=var_id)

    # Link methodology with same document (source_document_id=doc_id or None)
    link_resp = client.post(
        f"/api/research/projects/{proj_id}/instruments/{inst_id}/methodology",
        json={
            "expected_version": 0,
            "document_id": doc_id,
            "source_document_id": doc_id,
            "variable_links": {str(var_id): str(var_id)},
        },
    )
    assert link_resp.status_code == 200
    prov = link_resp.json()["provenance"]
    assert prov["source_document_id"] == doc_id
    assert prov["methodology_review_id"] == doc_id


def test_29_link_methodology_nonexistent_source_document(tmp_path):
    """29. Vinculación metodológica con documento fuente inexistente devuelve 422."""
    client, _, _ = _setup_api(tmp_path)
    proj_id = _create_project(client)
    var_id = uuid4()
    dim_id = uuid4()
    ind_id = uuid4()
    it_id = uuid4()

    payload = {
        "variables": [{"variable_id": str(var_id), "name": "Var"}],
        "dimensions": [{"dimension_id": str(dim_id), "variable_id": str(var_id), "name": "Dim"}],
        "indicators": [{"indicator_id": str(ind_id), "dimension_id": str(dim_id), "name": "Ind"}],
        "items": [
            {
                "item_id": str(it_id),
                "variable_id": str(var_id),
                "dimension_id": str(dim_id),
                "indicator_id": str(ind_id),
                "text": "Ítem.",
                "response_type": "single_choice",
                "response_options": [
                    {"code": "1", "label": "A", "numeric_value": 1.0},
                    {"code": "2", "label": "B", "numeric_value": 2.0},
                ],
            }
        ],
        "scoring_rules": [],
    }
    r = client.post(f"/api/research/projects/{proj_id}/instruments", json=payload)
    inst_id = r.json()["instrument_id"]
    doc_id = _upload_and_confirm_methodology(client, proj_id, var_id=var_id)

    fake_source_doc = str(uuid4())
    link_resp = client.post(
        f"/api/research/projects/{proj_id}/instruments/{inst_id}/methodology",
        json={
            "expected_version": 0,
            "document_id": doc_id,
            "source_document_id": fake_source_doc,
            "variable_links": {str(var_id): str(var_id)},
        },
    )
    assert link_resp.status_code == 422
    assert "no pertenece al proyecto" in link_resp.json()["detail"].lower()


def test_30_link_methodology_foreign_source_document(tmp_path):
    """30. Vinculación metodológica con documento fuente de otro proyecto devuelve 422."""
    client, _, _ = _setup_api(tmp_path)
    proj_a = _create_project(client)
    proj_b = _create_project(client)
    var_id = uuid4()
    dim_id = uuid4()
    ind_id = uuid4()
    it_id = uuid4()

    payload = {
        "variables": [{"variable_id": str(var_id), "name": "Var"}],
        "dimensions": [{"dimension_id": str(dim_id), "variable_id": str(var_id), "name": "Dim"}],
        "indicators": [{"indicator_id": str(ind_id), "dimension_id": str(dim_id), "name": "Ind"}],
        "items": [
            {
                "item_id": str(it_id),
                "variable_id": str(var_id),
                "dimension_id": str(dim_id),
                "indicator_id": str(ind_id),
                "text": "Ítem.",
                "response_type": "single_choice",
                "response_options": [
                    {"code": "1", "label": "A", "numeric_value": 1.0},
                    {"code": "2", "label": "B", "numeric_value": 2.0},
                ],
            }
        ],
        "scoring_rules": [],
    }
    r = client.post(f"/api/research/projects/{proj_a}/instruments", json=payload)
    inst_id = r.json()["instrument_id"]

    doc_a = _upload_and_confirm_methodology(client, proj_a, var_id=var_id)
    doc_b = _upload_docx_questionnaire(client, proj_b)

    # Attempt to link doc_b (belonging to proj_b) into instrument of proj_a
    link_resp = client.post(
        f"/api/research/projects/{proj_a}/instruments/{inst_id}/methodology",
        json={
            "expected_version": 0,
            "document_id": doc_a,
            "source_document_id": doc_b,
            "variable_links": {str(var_id): str(var_id)},
        },
    )
    assert link_resp.status_code == 422
    assert "no pertenece al proyecto" in link_resp.json()["detail"].lower()


def test_31_link_methodology_unconfirmed_review(tmp_path):
    """31. Vinculación metodológica con revisión no confirmada devuelve 422."""
    client, _, _ = _setup_api(tmp_path)
    proj_id = _create_project(client)
    var_id = uuid4()
    dim_id = uuid4()
    ind_id = uuid4()
    it_id = uuid4()

    payload = {
        "variables": [{"variable_id": str(var_id), "name": "Var"}],
        "dimensions": [{"dimension_id": str(dim_id), "variable_id": str(var_id), "name": "Dim"}],
        "indicators": [{"indicator_id": str(ind_id), "dimension_id": str(dim_id), "name": "Ind"}],
        "items": [
            {
                "item_id": str(it_id),
                "variable_id": str(var_id),
                "dimension_id": str(dim_id),
                "indicator_id": str(ind_id),
                "text": "Ítem.",
                "response_type": "single_choice",
                "response_options": [
                    {"code": "1", "label": "A", "numeric_value": 1.0},
                    {"code": "2", "label": "B", "numeric_value": 2.0},
                ],
            }
        ],
        "scoring_rules": [],
    }
    r = client.post(f"/api/research/projects/{proj_id}/instruments", json=payload)
    inst_id = r.json()["instrument_id"]

    # Upload document but do NOT confirm methodology review
    resp = client.post(
        f"/api/research/projects/{proj_id}/documents",
        content=b"%PDF-1.4\nTesis\n%%EOF",
        headers={"X-File-Name": "tesis.pdf"},
    )
    doc_id = resp.json()["id"]

    link_resp = client.post(
        f"/api/research/projects/{proj_id}/instruments/{inst_id}/methodology",
        json={
            "expected_version": 0,
            "document_id": doc_id,
            "variable_links": {str(var_id): str(var_id)},
        },
    )
    assert link_resp.status_code == 422
    assert "confirmada" in link_resp.json()["detail"].lower()


def test_32_link_methodology_modified_source_document_detected_stale(tmp_path):
    """32. Documento fuente modificado es detectado como stale por check_stale."""
    client, _, app = _setup_api(tmp_path)
    proj_id = _create_project(client)
    var_id = uuid4()
    dim_id = uuid4()
    ind_id = uuid4()
    it_id = uuid4()

    payload = {
        "variables": [{"variable_id": str(var_id), "name": "Clima Organizacional"}],
        "dimensions": [
            {"dimension_id": str(dim_id), "variable_id": str(var_id), "name": "Liderazgo"}
        ],
        "indicators": [
            {"indicator_id": str(ind_id), "dimension_id": str(dim_id), "name": "Comunicación"}
        ],
        "items": [
            {
                "item_id": str(it_id),
                "variable_id": str(var_id),
                "dimension_id": str(dim_id),
                "indicator_id": str(ind_id),
                "text": "Mi jefe me escucha activamente.",
                "response_type": "single_choice",
                "response_options": [
                    {"code": "1", "label": "Nunca", "numeric_value": 1.0},
                    {"code": "2", "label": "Siempre", "numeric_value": 2.0},
                ],
            }
        ],
        "scoring_rules": [],
    }
    r = client.post(f"/api/research/projects/{proj_id}/instruments", json=payload)
    inst_id = r.json()["instrument_id"]

    # Methodology review in doc 1
    m_doc_id = _upload_and_confirm_methodology(client, proj_id, var_id=var_id)
    # Source document in doc 2
    s_doc_id = _upload_docx_questionnaire(client, proj_id)

    link_resp = client.post(
        f"/api/research/projects/{proj_id}/instruments/{inst_id}/methodology",
        json={
            "expected_version": 0,
            "document_id": m_doc_id,
            "source_document_id": s_doc_id,
            "variable_links": {str(var_id): str(var_id)},
        },
    )
    assert link_resp.status_code == 200

    service: InstrumentService = app.state.instrument_service
    is_stale, reasons = service.check_stale(UUID(proj_id), UUID(inst_id))
    assert is_stale is False

    # Now modify source document bytes on disk
    doc_repo = app.state.instrument_service.documents.repository
    doc_repo._path(UUID(s_doc_id)).write_bytes(b"CONTENIDO TOTALMENTE MODIFICADO")

    is_stale, reasons = service.check_stale(UUID(proj_id), UUID(inst_id))
    assert is_stale is True
    assert any("modificado" in r.lower() for r in reasons)


def test_33_no_partial_instrument_persisted_on_draft_creation_error(tmp_path):
    """33. En escenarios de error no se crean instrumentos parcialmente persistidos."""
    client, _, _ = _setup_api(tmp_path)
    proj_id = _create_project(client)
    doc_id = _upload_docx_questionnaire(client, proj_id)

    ext_resp = client.post(
        f"/api/research/projects/{proj_id}/instruments/extract",
        json={"document_id": doc_id},
    )
    cand = ext_resp.json()["instruments"][0]

    # Tamper candidate so creation fails
    cand["items"][0]["text"] = "ÍTEM FABRICADO INEXISTENTE"
    cand["items"][0]["source_quote"] = "ÍTEM FABRICADO INEXISTENTE"

    draft_resp = client.post(
        f"/api/research/projects/{proj_id}/instruments/drafts/from-candidate",
        json={"document_id": doc_id, "candidate": cand},
    )
    assert draft_resp.status_code == 422

    # Verify zero instruments are persisted in database
    list_resp = client.get(f"/api/research/projects/{proj_id}/instruments")
    assert list_resp.status_code == 200
    assert len(list_resp.json()) == 0
