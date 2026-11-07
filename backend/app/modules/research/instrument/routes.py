"""FastAPI router for research instruments development endpoints."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Query, Response, status
from pydantic import BaseModel, ConfigDict, Field

from app.modules.research.instrument.contracts import InstrumentContext
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


def create_router(service: InstrumentService) -> APIRouter:
    router = APIRouter(
        prefix="/api/research/projects/{project_id}/instruments",
        tags=["Research instruments (development)"],
    )

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
