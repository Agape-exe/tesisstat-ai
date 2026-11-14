from uuid import UUID

from fastapi import APIRouter, status

from app.modules.research.preparation.models import (
    ApplyRequest,
    Plan,
    PreparationPreview,
    PreparationRecord,
)
from app.modules.research.preparation.use_cases import PreparationService


def create_router(service: PreparationService) -> APIRouter:
    router = APIRouter(
        prefix="/api/research/projects/{project_id}/datasets/{dataset_id}/preparation",
        tags=["Research preparation (development)"],
    )

    @router.post("/preview", response_model=PreparationPreview)
    def preview(project_id: UUID, dataset_id: UUID, plan: Plan) -> PreparationPreview:
        return service.preview(project_id, dataset_id, plan)

    @router.post("/apply", response_model=PreparationRecord, status_code=status.HTTP_201_CREATED)
    def apply(project_id: UUID, dataset_id: UUID, request: ApplyRequest) -> PreparationRecord:
        return service.apply(project_id, dataset_id, request)

    @router.get("s", response_model=list[PreparationRecord])
    def history(project_id: UUID, dataset_id: UUID) -> list[PreparationRecord]:
        return service.list(project_id, dataset_id)

    return router
