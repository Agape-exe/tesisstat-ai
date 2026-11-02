from urllib.parse import unquote
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, Request, Response, status
from pydantic import BaseModel, ConfigDict

from app.modules.research.datasets.models import Dataset, DatasetPreview
from app.modules.research.datasets.readers import InvalidDataset
from app.modules.research.datasets.use_cases import DatasetService


class DatasetOrigin(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    synthetic: bool


def create_router(service: DatasetService) -> APIRouter:
    router = APIRouter(
        prefix="/api/research/projects/{project_id}/datasets",
        tags=["Research datasets (development)"],
    )

    @router.post("", response_model=Dataset, status_code=status.HTTP_201_CREATED)
    async def add_dataset(
        project_id: UUID, request: Request, x_file_name: str = Header(default="")
    ) -> Dataset:
        data = bytearray()
        async for chunk in request.stream():
            data.extend(chunk)
            if len(data) > service.limits.max_bytes:
                raise InvalidDataset("El archivo supera el límite de 10 MiB.")
        return service.add(project_id, unquote(x_file_name), bytes(data))

    @router.get("", response_model=list[Dataset])
    def list_datasets(project_id: UUID) -> list[Dataset]:
        return service.list(project_id)

    @router.get("/{dataset_id}", response_model=Dataset)
    def get_dataset(project_id: UUID, dataset_id: UUID) -> Dataset:
        return service.get(project_id, dataset_id)

    @router.get("/{dataset_id}/preview", response_model=DatasetPreview)
    def preview_dataset(project_id: UUID, dataset_id: UUID) -> DatasetPreview:
        return service.preview(project_id, dataset_id)

    @router.post("/{dataset_id}/activate", response_model=Dataset)
    def activate_dataset(project_id: UUID, dataset_id: UUID) -> Dataset:
        return service.activate(project_id, dataset_id)

    @router.put("/{dataset_id}/origin", response_model=Dataset)
    def set_origin(project_id: UUID, dataset_id: UUID, origin: DatasetOrigin) -> Dataset:
        try:
            return service.set_synthetic(project_id, dataset_id, origin.synthetic)
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc

    @router.delete("/{dataset_id}", status_code=status.HTTP_204_NO_CONTENT)
    def delete_dataset(project_id: UUID, dataset_id: UUID) -> Response:
        service.delete(project_id, dataset_id)
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    return router
