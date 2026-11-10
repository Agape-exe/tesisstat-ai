from fastapi import APIRouter

from app.modules.research.intents.models import DiagnosticRequest, IntentPatch
from app.shared.analysis_v2 import AnalysisIntentV2
from app.shared.diagnostics_v2 import DiagnosticV2


def create_router(intents, diagnostics):
    router = APIRouter(
        prefix="/api/v2/research/projects/{project_id}", tags=["analysis-evidence-v2"]
    )

    @router.get("/intents", response_model=list[AnalysisIntentV2])
    def list_intents(project_id: str):
        return intents.list(project_id)

    @router.post("/intents", response_model=AnalysisIntentV2, status_code=201)
    def create_intent(project_id: str, body: IntentPatch):
        return intents.save(project_id, body)

    @router.get("/intents/{intent_id}", response_model=AnalysisIntentV2)
    def get_intent(project_id: str, intent_id: str):
        return intents.get(project_id, intent_id)

    @router.patch("/intents/{intent_id}", response_model=AnalysisIntentV2)
    def edit_intent(project_id: str, intent_id: str, body: IntentPatch):
        return intents.save(project_id, body, intent_id)

    @router.get("/intents/{intent_id}/revisions", response_model=list[AnalysisIntentV2])
    def revisions(project_id: str, intent_id: str):
        return intents.revisions(project_id, intent_id)

    @router.post("/diagnostics", response_model=DiagnosticV2, status_code=201)
    def create_diagnostic(project_id: str, body: DiagnosticRequest):
        return diagnostics.create(project_id, body)

    @router.get("/diagnostics", response_model=list[DiagnosticV2])
    def list_diagnostics(project_id: str, intent_id: str | None = None):
        return diagnostics.list(project_id, intent_id)

    @router.get("/diagnostics/{diagnostic_id}", response_model=DiagnosticV2)
    def get_diagnostic(project_id: str, diagnostic_id: str):
        return diagnostics.get(project_id, diagnostic_id)

    return router
