from datetime import UTC, datetime
from pathlib import PurePath
from uuid import UUID, uuid4

from app.modules.research.datasets.models import Dataset, DatasetPreview
from app.modules.research.datasets.readers import DatasetLimits, InvalidDataset, read_csv, read_xlsx
from app.modules.research.datasets.repository import DatasetRepository
from app.modules.research.projects.use_cases import ProjectService


class DatasetNotFound(Exception):
    pass


class DatasetService:
    def __init__(
        self,
        repository: DatasetRepository,
        projects: ProjectService,
        limits: DatasetLimits | None = None,
    ) -> None:
        self.repository = repository
        self.projects = projects
        self.limits = limits or DatasetLimits()

    def add(self, project_id: UUID, name: str, data: bytes) -> Dataset:
        self.projects.get(project_id)
        safe_name = PurePath(name.replace("\\", "/")).name
        if (
            not safe_name
            or safe_name in {".", ".."}
            or any(ord(char) < 32 for char in safe_name)
            or len(safe_name) > 255
        ):
            raise InvalidDataset("El nombre del archivo no es válido.")
        if not data:
            raise InvalidDataset("El archivo está vacío.")
        if len(data) > self.limits.max_bytes:
            raise InvalidDataset("El archivo supera el límite de 10 MiB.")
        extension = PurePath(safe_name).suffix.lower()
        if extension == ".csv":
            if data.startswith(b"PK\x03\x04") or b"\x00" in data:
                raise InvalidDataset("El contenido no corresponde a un CSV.")
            preview = read_csv(data, self.limits)
        elif extension == ".xlsx":
            if not data.startswith(b"PK\x03\x04"):
                raise InvalidDataset("El contenido no corresponde a un XLSX.")
            preview = read_xlsx(data, self.limits)
        else:
            raise InvalidDataset("Adjunta un archivo CSV o XLSX.")
        dataset = Dataset(
            id=uuid4(),
            project_id=project_id,
            name=safe_name,
            format=preview.format,
            size=len(data),
            row_count=preview.row_count,
            column_count=preview.column_count,
            columns=preview.columns,
            sheet=preview.sheet,
            uploaded_at=datetime.now(UTC),
            warnings=preview.warnings,
        )
        self.repository.add(dataset, preview, data)
        return dataset

    def list(self, project_id: UUID) -> list[Dataset]:
        self.projects.get(project_id)
        return self.repository.list(project_id)

    def get(self, project_id: UUID, dataset_id: UUID) -> Dataset:
        self.projects.get(project_id)
        result = self.repository.get(project_id, dataset_id)
        if result is None:
            raise DatasetNotFound
        return result

    def preview(self, project_id: UUID, dataset_id: UUID) -> DatasetPreview:
        self.get(project_id, dataset_id)
        result = self.repository.preview(project_id, dataset_id)
        if result is None:
            raise DatasetNotFound
        return result

    def activate(self, project_id: UUID, dataset_id: UUID) -> Dataset:
        self.get(project_id, dataset_id)
        if not self.repository.activate(project_id, dataset_id):
            raise DatasetNotFound
        return self.get(project_id, dataset_id)

    def set_synthetic(self, project_id: UUID, dataset_id: UUID, synthetic: bool) -> Dataset:
        dataset = self.get(project_id, dataset_id)
        if dataset.source_dataset_id is not None:
            raise ValueError("La procedencia de un derivado se hereda del dataset original.")
        result = self.repository.set_synthetic(project_id, dataset_id, synthetic)
        if result is None:
            raise DatasetNotFound
        return result

    def delete(self, project_id: UUID, dataset_id: UUID) -> None:
        self.get(project_id, dataset_id)
        if not self.repository.delete(project_id, dataset_id):
            raise DatasetNotFound

    def read(self, project_id: UUID, dataset_id: UUID) -> bytes:
        """Controlled future integration point; callers use IDs, never arbitrary paths."""
        self.get(project_id, dataset_id)
        return self.repository.read(project_id, dataset_id)
