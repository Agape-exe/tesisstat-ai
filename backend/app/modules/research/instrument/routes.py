"""FastAPI router for research instruments development endpoints."""

from __future__ import annotations

import hashlib
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Response, status
from pydantic import BaseModel, ConfigDict, Field

from app.modules.research.instrument.contracts import InstrumentContext
from app.modules.research.instrument.extraction_models import (
    CandidateInstrument,
    DocumentInstrumentExtraction,
)
from app.modules.research.instrument.extraction_service import InstrumentExtractionService
from app.modules.research.instrument.models import (
    InstrumentDimension,
    InstrumentIndicator,
    InstrumentItem,
    InstrumentProvenance,
    InstrumentVariable,
    ItemColumnMapping,
    ScoringRule,
)
from app.modules.research.instrument.service import InstrumentService


class CreateInstrumentDraftRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    variables: list[InstrumentVariable] = Field(min_length=1)
    dimensions: list[InstrumentDimension] = Field(min_length=1)
    indicators: list[InstrumentIndicator] = Field(min_length=1)
    items: list[InstrumentItem] = Field(min_length=1)
    scoring_rules: list[ScoringRule] | None = None
    provenance: InstrumentProvenance | None = None


class UpdateInstrumentDraftRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_version: int = Field(ge=0)
    variables: list[InstrumentVariable] = Field(min_length=1)
    dimensions: list[InstrumentDimension] = Field(min_length=1)
    indicators: list[InstrumentIndicator] = Field(min_length=1)
    items: list[InstrumentItem] = Field(min_length=1)
    scoring_rules: list[ScoringRule] | None = None


class LinkMethodologyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_version: int = Field(ge=0)
    document_id: UUID
    variable_links: dict[UUID, UUID] | None = None
    source_document_id: UUID | None = None


class ExtractInstrumentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document_id: UUID
    external_ai_consent: bool = False
    methodology_document_id: UUID | None = None


class CreateDraftFromCandidateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document_id: UUID
    candidate: CandidateInstrument
    methodology_document_id: UUID | None = None
    expected_document_hash: str | None = None


class ConfirmScoringRulesRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_version: int = Field(ge=0)
    rule_ids: list[UUID] | None = None


class MarkStaleRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_version: int = Field(ge=0)
    reasons: list[str] | None = None


class ConfirmInstrumentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_version: int = Field(ge=0)
    confirmer_ref: str = Field(
        min_length=1,
        max_length=200,
        description="Identificador referencial no autenticado provisto por el cliente.",
    )


class SetMappingRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_version: int = Field(ge=0)
    dataset_id: UUID
    item_columns: list[ItemColumnMapping] = Field(min_length=1)


class ConfirmMappingRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_version: int = Field(ge=0)
    confirmer_ref: str = Field(
        min_length=1,
        max_length=200,
        description="Identificador referencial no autenticado provisto por el cliente.",
    )


def create_router(
    service: InstrumentService,
    extraction_service: InstrumentExtractionService | None = None,
) -> APIRouter:
    router = APIRouter(
        prefix="/api/research/projects/{project_id}/instruments",
        tags=["Research instruments (development)"],
    )

    @router.post("/extract", response_model=DocumentInstrumentExtraction)
    def extract_instruments(
        project_id: UUID,
        payload: ExtractInstrumentRequest,
    ) -> DocumentInstrumentExtraction:
        if extraction_service is None:
            raise HTTPException(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                "El servicio de extracción de instrumentos no está configurado.",
            )
        result = extraction_service.extract(
            project_id=project_id,
            document_id=payload.document_id,
            external_ai_consent=payload.external_ai_consent,
            methodology_document_id=payload.methodology_document_id,
            strict_consent=True,
        )
        if result.status == "failed":
            for warning in result.warnings:
                if "not_configured" in warning.lower():
                    raise HTTPException(
                        status.HTTP_503_SERVICE_UNAVAILABLE,
                        "El proveedor de IA no está configurado.",
                    )
                if "quota" in warning.lower() or "input_limit" in warning.lower():
                    raise HTTPException(
                        status.HTTP_429_TOO_MANY_REQUESTS,
                        "Límite de cuota o presupuesto del proveedor de IA excedido.",
                    )
                if "timeout" in warning.lower():
                    raise HTTPException(
                        status.HTTP_504_GATEWAY_TIMEOUT,
                        "El proveedor de IA tardó demasiado en responder.",
                    )
                if "esquema estructurado" in warning.lower():
                    raise HTTPException(
                        status.HTTP_502_BAD_GATEWAY,
                        "La respuesta del proveedor de IA no cumple con el esquema estructurado.",
                    )
        return result

    @router.post(
        "/drafts/from-candidate",
        response_model=InstrumentContext,
        status_code=status.HTTP_201_CREATED,
    )
    def create_draft_from_candidate(
        project_id: UUID,
        payload: CreateDraftFromCandidateRequest,
        response: Response,
    ) -> InstrumentContext:
        if extraction_service is None:
            raise HTTPException(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                "El servicio de extracción de instrumentos no está configurado.",
            )

        # 1. Verificar documento en proyecto y obtener bytes actuales
        extraction_service._get_document(project_id, payload.document_id)
        doc_bytes = extraction_service._read_document_bytes(project_id, payload.document_id)
        current_doc_hash = hashlib.sha256(doc_bytes).hexdigest()

        # 2. Verificar hash stale si el cliente especificó un hash esperado
        if (
            payload.expected_document_hash is not None
            and payload.expected_document_hash != current_doc_hash
        ):
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                "El documento fuente ha sido modificado desde la extracción original (hash stale).",
            )

        # 3. Validación estructural canónica
        is_valid, reasons = extraction_service.can_convert_to_canonical(payload.candidate)
        if not is_valid:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                "El candidato no cumple los requisitos canónicos para crear un borrador: "
                f"{', '.join(reasons)}",
            )

        # 4. Verificación de integridad y evidencias contra el texto fuente
        text_result = extraction_service.extraction_service.extract(project_id, payload.document_id)
        if text_result.status != "completed" or not text_result.text:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                "El documento fuente no cuenta con texto extraído válido para "
                "verificar las evidencias.",
            )
        source_text = text_result.text

        # Comprobar que los ítems del candidato no fueron fabricados ni manipulados
        for item in payload.candidate.items:
            quote_to_check = item.source_quote or item.text
            if quote_to_check not in source_text:
                raise HTTPException(
                    status.HTTP_422_UNPROCESSABLE_CONTENT,
                    f"La evidencia del ítem '{item.text}' no fue encontrada en el texto "
                    "del documento fuente.",
                )

        # Comprobar evidencias de variables y dimensiones
        for var in payload.candidate.variables:
            if var.evidence_quote and var.evidence_quote not in source_text:
                raise HTTPException(
                    status.HTTP_422_UNPROCESSABLE_CONTENT,
                    f"La evidencia de la variable '{var.name}' no fue encontrada en "
                    "el documento fuente.",
                )
        for dim in payload.candidate.dimensions:
            if dim.evidence_quote and dim.evidence_quote not in source_text:
                raise HTTPException(
                    status.HTTP_422_UNPROCESSABLE_CONTENT,
                    f"La evidencia de la dimensión '{dim.name}' no fue encontrada en "
                    "el documento fuente.",
                )
        for ind in payload.candidate.indicators:
            if ind.evidence_quote and ind.evidence_quote not in source_text:
                raise HTTPException(
                    status.HTTP_422_UNPROCESSABLE_CONTENT,
                    f"La evidencia del indicador '{ind.name}' no fue encontrada en "
                    "el documento fuente.",
                )

        # 5. Creación del borrador a través de InstrumentExtractionService
        instrument = extraction_service.create_draft_from_candidate(
            project_id=project_id,
            document_id=payload.document_id,
            candidate=payload.candidate,
            methodology_document_id=payload.methodology_document_id,
        )
        response.headers["Location"] = (
            f"/api/research/projects/{project_id}/instruments/{instrument.instrument_id}"
        )
        return instrument

    @router.post("", response_model=InstrumentContext, status_code=status.HTTP_201_CREATED)
    def create_draft(
        project_id: UUID,
        payload: CreateInstrumentDraftRequest,
        response: Response,
    ) -> InstrumentContext:
        instrument = service.create_draft(
            project_id=project_id,
            variables=payload.variables,
            dimensions=payload.dimensions,
            indicators=payload.indicators,
            items=payload.items,
            scoring_rules=payload.scoring_rules,
            provenance=payload.provenance,
        )
        response.headers["Location"] = (
            f"/api/research/projects/{project_id}/instruments/{instrument.instrument_id}"
        )
        return instrument

    @router.get("", response_model=list[InstrumentContext])
    def list_instruments(project_id: UUID) -> list[InstrumentContext]:
        return service.list(project_id)

    @router.get("/{instrument_id}", response_model=InstrumentContext)
    def get_instrument(
        project_id: UUID,
        instrument_id: UUID,
        version: int | None = Query(None, ge=0),
    ) -> InstrumentContext:
        return service.get(project_id, instrument_id, version=version)

    @router.put("/{instrument_id}", response_model=InstrumentContext)
    def update_draft(
        project_id: UUID,
        instrument_id: UUID,
        payload: UpdateInstrumentDraftRequest,
    ) -> InstrumentContext:
        return service.update_draft(
            project_id=project_id,
            instrument_id=instrument_id,
            expected_version=payload.expected_version,
            variables=payload.variables,
            dimensions=payload.dimensions,
            indicators=payload.indicators,
            items=payload.items,
            scoring_rules=payload.scoring_rules,
        )

    @router.post("/{instrument_id}/methodology", response_model=InstrumentContext)
    def link_methodology(
        project_id: UUID,
        instrument_id: UUID,
        payload: LinkMethodologyRequest,
    ) -> InstrumentContext:
        return service.link_methodology(
            project_id=project_id,
            instrument_id=instrument_id,
            expected_version=payload.expected_version,
            document_id=payload.document_id,
            variable_links=payload.variable_links,
            source_document_id=payload.source_document_id,
        )

    @router.post("/{instrument_id}/rules/confirm", response_model=InstrumentContext)
    def confirm_scoring_rules(
        project_id: UUID,
        instrument_id: UUID,
        payload: ConfirmScoringRulesRequest,
    ) -> InstrumentContext:
        return service.confirm_scoring_rules(
            project_id=project_id,
            instrument_id=instrument_id,
            expected_version=payload.expected_version,
            rule_ids=payload.rule_ids,
        )

    @router.post("/{instrument_id}/confirm", response_model=InstrumentContext)
    def confirm_instrument(
        project_id: UUID,
        instrument_id: UUID,
        payload: ConfirmInstrumentRequest,
    ) -> InstrumentContext:
        return service.confirm_instrument(
            project_id=project_id,
            instrument_id=instrument_id,
            expected_version=payload.expected_version,
            confirmer_ref=payload.confirmer_ref,
        )

    @router.post("/{instrument_id}/mark-stale", response_model=InstrumentContext)
    def mark_stale(
        project_id: UUID,
        instrument_id: UUID,
        payload: MarkStaleRequest,
    ) -> InstrumentContext:
        return service.mark_stale(
            project_id=project_id,
            instrument_id=instrument_id,
            expected_version=payload.expected_version,
            reasons=payload.reasons,
        )

    @router.post("/{instrument_id}/mapping", response_model=InstrumentContext)
    def set_mapping(
        project_id: UUID,
        instrument_id: UUID,
        payload: SetMappingRequest,
    ) -> InstrumentContext:
        return service.set_mapping(
            project_id=project_id,
            instrument_id=instrument_id,
            expected_version=payload.expected_version,
            dataset_id=payload.dataset_id,
            item_columns=payload.item_columns,
        )

    @router.post("/{instrument_id}/mapping/confirm", response_model=InstrumentContext)
    def confirm_mapping(
        project_id: UUID,
        instrument_id: UUID,
        payload: ConfirmMappingRequest,
    ) -> InstrumentContext:
        return service.confirm_mapping(
            project_id=project_id,
            instrument_id=instrument_id,
            expected_version=payload.expected_version,
            confirmer_ref=payload.confirmer_ref,
        )

    @router.get("/{instrument_id}/history", response_model=list[InstrumentContext])
    def get_history(
        project_id: UUID,
        instrument_id: UUID,
    ) -> list[InstrumentContext]:
        return service.get_history(project_id, instrument_id)

    return router
