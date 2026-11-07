"""Build only from reviewed, explicitly linked Research sources."""

import hashlib
from datetime import UTC, datetime
from uuid import UUID, uuid4

from fastapi import HTTPException
from pydantic import ValidationError

from app.modules.research.datasets.hashing import compute_dataset_hash
from app.modules.research.datasets.models import Dataset
from app.modules.research.datasets.use_cases import DatasetNotFound, DatasetService
from app.modules.research.documents.use_cases import DocumentService
from app.modules.research.methodology.models import MethodologyReview
from app.modules.research.methodology.review import ReviewService
from app.modules.research.packages.models import (
    PackageConfiguration,
    StoredPackage,
    ValidationStatus,
)
from app.modules.research.packages.repository import PackageRepository
from app.modules.research.projects.use_cases import ProjectService
from app.shared.contracts import (
    DatasetReference,
    ResearchHypothesis,
    ResearchPackage,
    ResearchVariable,
)


def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


class PackageService:
    def __init__(
        self,
        projects: ProjectService,
        documents: DocumentService,
        reviews: ReviewService,
        datasets: DatasetService,
        repository: PackageRepository,
    ):
        self.projects = projects
        self.documents = documents
        self.reviews = reviews
        self.datasets = datasets
        self.repository = repository

    def _sources(self, project_id: UUID, config: PackageConfiguration):
        review = None
        dataset = None
        if config.document_id:
            if config.document_id not in {doc.id for doc in self.documents.list(project_id)}:
                raise HTTPException(404, "El documento seleccionado no pertenece al proyecto.")
            review = self.reviews.get(project_id, config.document_id)
        if config.dataset_id:
            try:
                dataset = self.datasets.get(project_id, config.dataset_id)
            except DatasetNotFound as exc:
                raise HTTPException(
                    404, "El dataset seleccionado no pertenece al proyecto."
                ) from exc
        return review, dataset

    def _dataset_hash(self, project_id: UUID, dataset: Dataset) -> str:
        raw_bytes = self.datasets.read(project_id, dataset.id)
        return compute_dataset_hash(dataset, raw_bytes)

    @staticmethod
    def _review_hash(review: MethodologyReview) -> str:
        return digest(review.content.model_dump_json().encode())

    def configuration(self, project_id: UUID) -> PackageConfiguration:
        self.projects.get(project_id)
        stored = self.repository.get(project_id)
        return stored.configuration if stored else PackageConfiguration()

    def save(self, project_id: UUID, config: PackageConfiguration) -> PackageConfiguration:
        self.projects.get(project_id)
        current = self.repository.get(project_id)
        expected = current.configuration.version if current else 0
        if config.version != expected:
            raise HTTPException(409, "La configuración cambió. Recarga antes de guardar.")
        review, dataset = self._sources(project_id, config)
        if review and review.review_status != "reviewed":
            raise HTTPException(422, "Confirma la revisión metodológica seleccionada.")
        if dataset and not dataset.active:
            raise HTTPException(422, "Selecciona el dataset activo del proyecto.")
        config.review_version = review.version if review else None
        config.review_hash = self._review_hash(review) if review else None
        config.dataset_hash = self._dataset_hash(project_id, dataset) if dataset else None
        config.version = expected + 1
        config.updated_at = datetime.now(UTC)
        record = StoredPackage(
            project_id=project_id,
            configuration=config,
            package=current.package if current else None,
            warnings=current.warnings if current else [],
            built_at=current.built_at if current else None,
            built_configuration_version=current.built_configuration_version if current else None,
        )
        if not self.repository.save(record, expected if current else None):
            raise HTTPException(409, "La configuración cambió. Recarga antes de guardar.")
        return config

    def validate(self, project_id: UUID) -> ValidationStatus:
        self.projects.get(project_id)
        record = self.repository.get(project_id)
        config = record.configuration if record else PackageConfiguration()
        docs = self.documents.list(project_id)
        documents = []
        for doc in docs:
            review = self.reviews.get(project_id, doc.id)
            documents.append(
                {
                    "id": str(doc.id),
                    "name": doc.name,
                    "review_status": review.review_status if review else "missing",
                    "review_version": review.version if review else None,
                }
            )
        errors: list[str] = []
        warnings: list[str] = []
        review = (
            self.reviews.get(project_id, config.document_id)
            if config.document_id in {doc.id for doc in docs}
            else None
        )
        dataset = None
        if config.dataset_id:
            try:
                dataset = self.datasets.get(project_id, config.dataset_id)
            except DatasetNotFound:
                pass
        if config.document_id is None:
            errors.append("Selecciona un documento metodológico.")
        elif review is None or review.review_status != "reviewed":
            errors.append("La metodología seleccionada debe estar confirmada.")
        if config.dataset_id is None:
            errors.append("Activa y selecciona un dataset.")
        elif dataset is None or not dataset.active:
            errors.append("El dataset seleccionado ya no está activo.")
        if dataset and dataset.synthetic is None:
            errors.append("Declara si el dataset es sintético o no sintético.")
        stale = bool(
            (config.document_id and review is None) or (config.dataset_id and dataset is None)
        )
        if review and (
            config.review_version != review.version
            or config.review_hash != self._review_hash(review)
        ):
            stale = True
            errors.append(
                "La revisión metodológica cambió. Revisa las vinculaciones y guarda de nuevo."
            )
        if dataset and config.dataset_hash != self._dataset_hash(project_id, dataset):
            stale = True
            errors.append("El dataset cambió. Revisa las columnas y guarda de nuevo.")
        if review and review.review_status == "reviewed":
            content = review.content
            if not content.title.value or not content.title.value.strip():
                errors.append("La metodología no tiene un título válido.")
            variables = {str(item.id): item for item in content.variables}
            if not variables:
                errors.append("La metodología requiere al menos una variable.")
            linked_ids = [str(item.variable_id) for item in config.variables]
            if len(set(linked_ids)) != len(linked_ids) or set(linked_ids) != set(variables):
                errors.append("Vincula una sola vez cada variable revisada.")
            for link in config.variables:
                if not link.columns or len(set(link.columns)) != len(link.columns):
                    errors.append(
                        f"Selecciona columnas únicas para la variable {link.variable_id}."
                    )
                if dataset and not set(link.columns) <= set(dataset.columns):
                    errors.append(
                        f"La variable {link.variable_id} referencia columnas inexistentes."
                    )
            source_hypotheses = self._hypotheses(review)
            if not source_hypotheses:
                errors.append("La metodología requiere al menos una hipótesis explícita.")
            sources = [item.source for item in config.hypotheses]
            ids = [item.id for item in config.hypotheses]
            if (
                len(set(sources)) != len(sources)
                or set(sources) != set(source_hypotheses)
                or len(set(ids)) != len(ids)
            ):
                errors.append("Vincula cada hipótesis revisada con un ID único.")
            objectives = {item.value for item in content.specific_objectives if item.value}
            if content.general_objective.value:
                objectives.add(content.general_objective.value)
            for link in config.hypotheses:
                if not link.objective.strip() or link.objective not in objectives:
                    errors.append(f"Selecciona un objetivo revisado para la hipótesis {link.id}.")
                if not link.variable_ids or len(set(link.variable_ids)) != len(link.variable_ids):
                    errors.append(f"Selecciona variables únicas para la hipótesis {link.id}.")
                if not {str(item) for item in link.variable_ids} <= set(variables):
                    errors.append(f"La hipótesis {link.id} referencia variables inexistentes.")
            if content.clarifications:
                warnings.extend(item.value for item in content.clarifications if item.value)
            if review.pending_fields:
                warnings.append("La revisión contiene campos metodológicos pendientes.")
        if config.design == "unknown":
            warnings.append("Aclara el diseño de investigación antes de planificar estadísticas.")
        if config.observations == "unknown":
            warnings.append("Aclara la dependencia entre observaciones.")
        if any(item.measurement_scale == "unknown" for item in config.variables):
            warnings.append("Confirma las escalas de medición desconocidas.")
        if any(item.kind == "unknown" for item in config.hypotheses):
            warnings.append("Confirma los tipos de hipótesis desconocidos.")
        state = (
            "stale"
            if stale
            or (
                record
                and record.package
                and (errors or record.built_configuration_version != config.version)
            )
            else "incomplete"
            if errors
            else "generated"
            if record and record.package
            else "warnings"
            if warnings
            else "ready"
        )
        return ValidationStatus(
            state=state,
            errors=errors,
            warnings=warnings,
            configuration=config,
            documents=documents,
            dataset=dataset,
            review=review,
            package_id=record.package.id if record and record.package else None,
        )

    @staticmethod
    def _hypotheses(review: MethodologyReview) -> dict[str, str]:
        content = review.content
        result = {}
        if content.general_hypothesis.value:
            result["general"] = content.general_hypothesis.value
        result.update(
            {
                f"specific:{i}": item.value
                for i, item in enumerate(content.specific_hypotheses)
                if item.value
            }
        )
        return result

    def check(self, project_id: UUID) -> ValidationStatus:
        status = self.validate(project_id)
        record = self.repository.get(project_id)
        if record:
            record.validation_state = status.state
            record.validation_errors = status.errors
            record.validation_warnings = status.warnings
            record.validated_at = datetime.now(UTC)
            if not self.repository.save(record, record.configuration.version):
                raise HTTPException(409, "La configuración cambió durante la validación.")
        return status

    def build(self, project_id: UUID) -> ResearchPackage:
        status = self.validate(project_id)
        if status.errors:
            raise HTTPException(422, {"errors": status.errors, "warnings": status.warnings})
        config = status.configuration
        review = status.review
        dataset = status.dataset
        assert review is not None and dataset is not None
        source_variables = {item.id: item for item in review.content.variables}
        source_hypotheses = self._hypotheses(review)
        try:
            variables = [
                ResearchVariable(
                    schema_version="1.0.0",
                    id=str(link.variable_id),
                    name=source_variables[link.variable_id].name.value,
                    role=link.role,
                    measurement_scale=link.measurement_scale,
                    columns=link.columns,
                    dimensions=[
                        item.value
                        for item in source_variables[link.variable_id].dimensions
                        if item.value
                    ],
                    questions=[
                        item.value
                        for item in source_variables[link.variable_id].instrument_items
                        if item.value
                    ],
                )
                for link in config.variables
            ]
            hypotheses = [
                ResearchHypothesis(
                    schema_version="1.0.0",
                    id=str(link.id),
                    statement=source_hypotheses[link.source],
                    objective=link.objective,
                    kind=link.kind,
                    variable_ids=[str(item) for item in link.variable_ids],
                    null_statement=link.null_statement,
                    alternative=link.alternative,
                )
                for link in config.hypotheses
            ]
            package = ResearchPackage.model_validate(
                {
                    "schema_version": "1.0.0",
                    "id": str(uuid4()),
                    "title": review.content.title.value,
                    "methodology_status": "reviewed",
                    "design": config.design,
                    "observations": config.observations,
                    "sampling_notes": config.sampling_notes,
                    "variables": variables,
                    "hypotheses": hypotheses,
                    "dataset": DatasetReference(
                        schema_version="1.0.0",
                        id=str(dataset.id),
                        location=f"research-dataset:{dataset.id}",
                        format=dataset.format,
                        row_count=dataset.row_count,
                        columns=dataset.columns,
                        synthetic=dataset.synthetic,
                    ),
                    "pending_questions": status.warnings,
                }
            )
        except (ValidationError, KeyError, ValueError) as exc:
            raise HTTPException(
                422, "La configuración no cumple el contrato ResearchPackage."
            ) from exc
        record = self.repository.get(project_id)
        assert record is not None
        expected = record.configuration.version
        record.configuration.version += 1
        record.configuration.updated_at = datetime.now(UTC)
        record.package = package
        record.warnings = status.warnings
        record.built_at = datetime.now(UTC)
        record.built_configuration_version = record.configuration.version
        record.validation_state = "generated"
        record.validation_errors = []
        record.validation_warnings = status.warnings
        record.validated_at = record.built_at
        if not self.repository.save(record, expected):
            raise HTTPException(409, "La configuración cambió durante la construcción.")
        return package

    def get_package(self, project_id: UUID) -> ResearchPackage:
        status = self.validate(project_id)
        if status.state == "stale":
            raise HTTPException(409, "El paquete está desactualizado; revisa y reconstruye.")
        record = self.repository.get(project_id)
        if record is None or record.package is None:
            raise HTTPException(404, "Aún no se generó un paquete de investigación.")
        return ResearchPackage.model_validate(record.package.model_dump())

    def read_package(self, package_id: str) -> ResearchPackage:
        """Authorized integration can call this port after checking access to the project."""
        record = self.repository.find_package(package_id)
        if record is None:
            raise HTTPException(404, "No se encontró el paquete de investigación.")
        return self.get_package(record.project_id)
