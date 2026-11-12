from urllib.parse import quote, unquote

from fastapi import APIRouter, Header, Request, Response

from app.modules.research.sources.models import SheetPatch, TableContextPatch
from app.modules.research.sources.readers import limit
from app.modules.research.sources.service import SourceService
from app.shared.data_sources_v2 import (
    FormulaAuditV2,
    ImportedTableV2,
    SourceFileV2,
    TableContextV2,
    TablePreviewV2,
)


def create_router(service: SourceService):
    router = APIRouter(prefix="/api/v2/research/projects/{project_id}", tags=["sources-v2"])

    @router.get("/files", response_model=list[SourceFileV2])
    def files(project_id: str):
        return service.files(project_id)

    @router.post("/files", response_model=SourceFileV2, status_code=201)
    async def upload(project_id: str, request: Request, x_file_name: str = Header(default="")):
        service.require(project_id)
        data = bytearray()
        async for chunk in request.stream():
            data.extend(chunk)
            if len(data) > service.limits.max_bytes:
                limit("El archivo supera el límite de 10 MiB.")
        return service.add(project_id, unquote(x_file_name), bytes(data))

    @router.get("/files/{file_id}/original")
    def original(project_id: str, file_id: str):
        source, data = service.original(project_id, file_id)
        return Response(
            data,
            media_type="application/octet-stream",
            headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(source.name)}"},
        )

    @router.post("/files/{file_id}/reimport", response_model=SourceFileV2, status_code=201)
    def reimport(project_id: str, file_id: str):
        return service.reimport(project_id, file_id)

    @router.patch("/files/{file_id}/sheets/{sheet_id}", response_model=SourceFileV2)
    def sheet(project_id: str, file_id: str, sheet_id: str, body: SheetPatch):
        return service.change_sheet(project_id, file_id, sheet_id, body)

    @router.get("/tables", response_model=list[ImportedTableV2])
    def tables(project_id: str):
        return service.tables(project_id)

    @router.get("/table-contexts", response_model=list[TableContextV2])
    def contexts(project_id: str):
        return service.contexts(project_id)

    @router.get("/tables/{table_id}", response_model=ImportedTableV2)
    def table(project_id: str, table_id: str):
        return service.table(project_id, table_id)

    @router.get("/tables/{table_id}/preview", response_model=TablePreviewV2)
    def preview(project_id: str, table_id: str):
        return service.preview(project_id, table_id)

    @router.get("/tables/{table_id}/calculation", response_model=FormulaAuditV2 | None)
    def calculation(project_id: str, table_id: str):
        return service.calculation(project_id, table_id)

    @router.get("/tables/{table_id}/context", response_model=TableContextV2)
    def context(project_id: str, table_id: str):
        return service.context(project_id, table_id)

    @router.patch("/tables/{table_id}/context", response_model=TableContextV2)
    def patch_context(project_id: str, table_id: str, body: TableContextPatch):
        return service.patch_context(project_id, table_id, body)

    @router.get("/tables/{table_id}/context/revisions", response_model=list[TableContextV2])
    def context_revisions(project_id: str, table_id: str):
        return service.context_revisions(project_id, table_id)

    return router
