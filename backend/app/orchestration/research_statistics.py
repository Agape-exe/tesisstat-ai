"""Project-scoped Research inputs for an eventual Statistics consumer.

This is an internal service. The development app must not expose dataset bytes over HTTP.
"""

from uuid import UUID

from fastapi import HTTPException

from app.modules.research.datasets.readers import InvalidDataset, read_csv, read_xlsx
from app.modules.research.datasets.sqlite_repository import DatasetStorageError
from app.modules.research.datasets.use_cases import DatasetNotFound, DatasetService
from app.modules.research.packages.reader import PackageReaderAdapter
from app.modules.research.packages.use_cases import PackageService
from app.modules.research.projects.use_cases import ProjectNotFound, ProjectService
from app.shared.contracts import DatasetReference, ResearchPackage


class ResearchInputError(Exception):
    """A safe, typed failure at the Research/Statistics boundary."""

    def __init__(self, code: str, detail: str):
        self.code = code
        super().__init__(detail)


class ResearchStatisticsBridge:
    def __init__(
        self,
        projects: ProjectService,
        packages: PackageService,
        datasets: DatasetService,
    ) -> None:
        self.projects = projects
        self.packages = packages
        self.reader = PackageReaderAdapter(packages)
        self.datasets = datasets

    def get_package(self, project_id: UUID, package_id: str) -> ResearchPackage:
        """Read only the current package in the explicitly selected project."""
        try:
            self.projects.get(project_id)
            current = self.packages.get_package(project_id)
        except ProjectNotFound as exc:
            raise ResearchInputError("project_missing", "No se encontró el proyecto.") from exc
        except (DatasetStorageError, FileNotFoundError, InvalidDataset) as exc:
            raise ResearchInputError(
                "dataset_inaccessible", "El dataset no está disponible."
            ) from exc
        except HTTPException as exc:
            if exc.status_code == 404:
                code = "package_missing"
            else:
                selected = self.packages.validate(project_id).dataset
                code = (
                    "dataset_inaccessible"
                    if selected is None
                    else "dataset_inactive"
                    if not selected.active
                    else "package_stale"
                )
            raise ResearchInputError(code, "No hay un paquete vigente para el proyecto.") from exc
        if current.id != package_id:
            raise ResearchInputError(
                "package_missing", "No hay un paquete vigente para el proyecto."
            )
        # The existing reader port is used only after checking project ownership.
        try:
            read = self.reader.get_package(package_id)
        except HTTPException as exc:
            raise ResearchInputError("package_stale", "El paquete ya no está vigente.") from exc
        except (DatasetStorageError, FileNotFoundError, InvalidDataset) as exc:
            raise ResearchInputError(
                "dataset_inaccessible", "El dataset no está disponible."
            ) from exc
        if read != current:
            raise ResearchInputError("package_stale", "El paquete ya no está vigente.")
        return read

    def read_dataset(
        self, project_id: UUID, package: ResearchPackage, reference: DatasetReference
    ) -> bytes:
        """Resolve a validated opaque key to bytes without accepting a filesystem path."""
        current = self.get_package(project_id, package.id)
        if package != current:
            raise ResearchInputError("package_stale", "El paquete ya no está vigente.")
        try:
            dataset_id = UUID(reference.id)
        except (ValueError, AttributeError) as exc:
            raise ResearchInputError(
                "invalid_reference", "La referencia del dataset no es válida."
            ) from exc
        if (
            str(dataset_id) != reference.id
            or reference.location != f"research-dataset:{dataset_id}"
            or reference.id != current.dataset.id
        ):
            raise ResearchInputError("invalid_reference", "La referencia del dataset no es válida.")
        if reference != current.dataset:
            raise ResearchInputError(
                "dataset_incompatible", "El dataset no coincide con el paquete."
            )
        try:
            dataset = self.datasets.get(project_id, dataset_id)
        except DatasetNotFound as exc:
            raise ResearchInputError(
                "dataset_inaccessible", "El dataset no está disponible."
            ) from exc
        if not dataset.active:
            raise ResearchInputError(
                "dataset_inactive", "El dataset seleccionado ya no está activo."
            )
        if (
            dataset.project_id != project_id
            or str(dataset.id) != reference.id
            or dataset.format != reference.format
            or dataset.columns != reference.columns
            or dataset.row_count != reference.row_count
            or dataset.synthetic != reference.synthetic
        ):
            raise ResearchInputError(
                "dataset_incompatible", "El dataset no coincide con el paquete."
            )
        try:
            data = self.datasets.read(project_id, dataset_id)
            preview = (
                read_csv(data, self.datasets.limits)
                if reference.format == "csv"
                else read_xlsx(data, self.datasets.limits)
            )
        except (DatasetNotFound, DatasetStorageError, FileNotFoundError, OSError) as exc:
            raise ResearchInputError(
                "dataset_inaccessible", "El dataset no está disponible."
            ) from exc
        except InvalidDataset as exc:
            raise ResearchInputError(
                "dataset_incompatible", "El dataset no coincide con el paquete."
            ) from exc
        if (
            len(data) != dataset.size
            or preview.format != reference.format
            or preview.columns != reference.columns
            or preview.row_count != reference.row_count
        ):
            raise ResearchInputError(
                "dataset_incompatible", "El dataset no coincide con el paquete."
            )
        # A second freshness check also catches source changes during the read.
        if self.get_package(project_id, package.id) != current:
            raise ResearchInputError("package_stale", "El paquete ya no está vigente.")
        return data
