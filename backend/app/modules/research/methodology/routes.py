from typing import Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException

from app.modules.research.methodology.models import (
    MethodologyDraft,
    MethodologyReview,
    MethodologyState,
    ReviewUpdate,
    StrictModel,
)
from app.modules.research.methodology.review import ReviewService
from app.modules.research.methodology.service import MESSAGES, MethodologyService
from app.shared.ai_errors import AIError


class AnalysisConsent(StrictModel):
    send_to_external_ai: Literal[True]


class ReviewVersion(StrictModel):
    version: int


def create_router(service: MethodologyService, reviews: ReviewService) -> APIRouter:
    router = APIRouter(
        prefix="/api/research/projects/{project_id}/documents/{document_id}",
        tags=["Research methodology (development)"],
    )

    @router.get("/methodology/status", response_model=MethodologyState)
    def status(project_id: UUID, document_id: UUID):
        return service.get(project_id, document_id)

    @router.get("/methodology", response_model=MethodologyDraft)
    def result(project_id: UUID, document_id: UUID):
        state = service.get(project_id, document_id)
        if state.draft is None:
            raise HTTPException(404, "Aún no hay borrador metodológico para este documento.")
        return state.draft

    @router.post("/methodology/extract", response_model=MethodologyState)
    def analyze(project_id: UUID, document_id: UUID, consent: AnalysisConsent):
        try:
            return service.analyze(project_id, document_id)
        except AIError as exc:
            code = (
                422
                if exc.code == "no_text"
                else 409
                if exc.code in ("busy", "retry_limit")
                else 503
            )
            raise HTTPException(code, MESSAGES.get(exc.code, MESSAGES["provider_error"])) from None

    @router.get("/methodology/review", response_model=MethodologyReview)
    def review(project_id: UUID, document_id: UUID):
        result = reviews.get(project_id, document_id)
        if result is None:
            raise HTTPException(404, "Aún no hay metodología editable.")
        return result

    @router.get("/methodology/review/status", response_model=MethodologyReview | None)
    def review_status(project_id: UUID, document_id: UUID):
        return reviews.get(project_id, document_id)

    @router.post("/methodology/review", response_model=MethodologyReview, status_code=201)
    def create_review(project_id: UUID, document_id: UUID):
        return reviews.create(project_id, document_id)

    @router.put("/methodology/review", response_model=MethodologyReview)
    def save_review(project_id: UUID, document_id: UUID, update: ReviewUpdate):
        return reviews.save(project_id, document_id, update)

    @router.post("/methodology/review/confirm", response_model=MethodologyReview)
    def confirm_review(project_id: UUID, document_id: UUID, request: ReviewVersion):
        return reviews.confirm(project_id, document_id, request.version)

    return router
