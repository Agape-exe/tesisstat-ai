from fastapi import APIRouter

from app.modules.research.context.import_models import (
    ContextSuggestion,
    SuggestionApply,
    SuggestionCreate,
)
from app.modules.research.context.models import ContextPatch
from app.modules.research.context.prompt import MASTER_PROMPT, PROMPT_VERSION
from app.modules.research.context.suggestions import SuggestionService
from app.modules.research.context.use_cases import ContextService
from app.shared.analysis_v2 import ProjectContextV2


def create_router(service: ContextService) -> APIRouter:
    router = APIRouter(prefix="/api/v2/research/projects/{project_id}/context", tags=["context-v2"])
    suggestions = SuggestionService(service)

    @router.get("/import-prompt")
    def prompt(project_id: str):
        service._require(project_id)
        return {
            "format_version": "context-import-1.0",
            "prompt_version": PROMPT_VERSION,
            "prompt": MASTER_PROMPT,
        }

    @router.post("/suggestions", response_model=ContextSuggestion, status_code=201)
    def create_suggestion(project_id: str, body: SuggestionCreate):
        return suggestions.create(project_id, body)

    @router.get("/suggestions", response_model=list[ContextSuggestion])
    def list_suggestions(project_id: str):
        return suggestions.list(project_id)

    @router.get("/suggestions/{suggestion_id}", response_model=ContextSuggestion)
    def get_suggestion(project_id: str, suggestion_id: str):
        return suggestions.get(project_id, suggestion_id)

    @router.post("/suggestions/{suggestion_id}/reject", response_model=ContextSuggestion)
    def reject_suggestion(project_id: str, suggestion_id: str):
        return suggestions.reject(project_id, suggestion_id)

    @router.post("/suggestions/{suggestion_id}/apply", response_model=ContextSuggestion)
    def apply_suggestion(project_id: str, suggestion_id: str, body: SuggestionApply):
        return suggestions.apply(project_id, suggestion_id, body)

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
