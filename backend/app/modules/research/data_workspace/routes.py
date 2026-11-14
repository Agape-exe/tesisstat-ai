from fastapi import APIRouter

from app.modules.research.data_workspace.models import ApplyRequest, DictionaryPatch, ProfileRequest
from app.shared.data_workspace_v2 import (
    DatasetRefV2,
    DerivedTableV2,
    PreparationPreviewV2,
    TableProfileV2,
    TableRecipeV2,
    VariableDictionaryV2,
)
from app.shared.instruments_v2 import ScoreDerivedTableV2


def create_router(service):
    router = APIRouter(prefix="/api/v2/research/projects/{project_id}", tags=["data-workspace-v2"])

    @router.get("/data-tables", response_model=list[DatasetRefV2])
    def tables(project_id: str):
        return service.datasets(project_id)

    @router.get("/data-summary")
    def summary(project_id: str):
        return service.summary(project_id)

    @router.get("/data-tables/{table_id}/preview")
    def preview(project_id: str, table_id: str):
        dataset, rows = service.read_table(project_id, table_id)
        return {"dataset_ref": dataset, "rows": rows[:20]}

    @router.get("/data-tables/{table_id}/dictionary", response_model=VariableDictionaryV2)
    def dictionary(project_id: str, table_id: str):
        return service.dictionary(project_id, table_id)

    @router.patch("/data-tables/{table_id}/dictionary", response_model=VariableDictionaryV2)
    def patch(project_id: str, table_id: str, body: DictionaryPatch):
        return service.patch_dictionary(project_id, table_id, body)

    @router.get(
        "/data-tables/{table_id}/dictionary/revisions", response_model=list[VariableDictionaryV2]
    )
    def dictionaries(project_id: str, table_id: str):
        service.history_access(project_id, table_id)
        return service.repository.revisions(project_id, "dictionary", table_id)

    @router.get("/data-tables/{table_id}/profile", response_model=TableProfileV2)
    def profile(project_id: str, table_id: str):
        return service.profile(project_id, table_id)

    @router.post("/data-tables/{table_id}/profile", response_model=TableProfileV2, status_code=201)
    def compute(project_id: str, table_id: str, body: ProfileRequest):
        return service.compute_profile(project_id, table_id, body)

    @router.get("/data-tables/{table_id}/profile/revisions", response_model=list[TableProfileV2])
    def profiles(project_id: str, table_id: str):
        service.history_access(project_id, table_id)
        return service.repository.revisions(project_id, "profile", table_id)

    @router.post(
        "/table-preparations/preview", response_model=PreparationPreviewV2, status_code=201
    )
    def prepare(project_id: str, body: TableRecipeV2):
        return service.preview(project_id, body)

    @router.post("/table-preparations/apply", response_model=DerivedTableV2, status_code=201)
    def apply(project_id: str, body: ApplyRequest):
        return service.apply(project_id, body)

    @router.get("/derived-tables/{table_id}", response_model=DerivedTableV2 | ScoreDerivedTableV2)
    def derived(project_id: str, table_id: str):
        return service.derived(project_id, table_id)

    return router
