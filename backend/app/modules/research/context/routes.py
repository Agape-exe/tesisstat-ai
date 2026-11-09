from fastapi import APIRouter

from app.modules.research.context.models import ContextPatch
from app.modules.research.context.use_cases import ContextService
from app.shared.analysis_v2 import ProjectContextV2


def create_router(service: ContextService) -> APIRouter:
    router = APIRouter(prefix="/api/v2/research/projects/{project_id}/context", tags=["context-v2"])

    @router.get("", response_model=ProjectContextV2)
    def get(project_id: str):
        return service.get(project_id)

    @router.patch("", response_model=ProjectContextV2)
    def patch(project_id: str, body: ContextPatch):
        return service.patch(project_id, body)

    @router.get("/revisions", response_model=list[ProjectContextV2])
    def revisions(project_id: str):
        return service.revisions(project_id)

    return router
