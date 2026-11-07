"""Application service for research instruments management and lifecycle."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from uuid import UUID, uuid4

from app.modules.research.datasets.models import Dataset
from app.modules.research.datasets.use_cases import DatasetNotFound, DatasetService
from app.modules.research.documents.use_cases import DocumentService
from app.modules.research.instrument.contracts import InstrumentContext
from app.modules.research.instrument.models import (
    DatasetMapping,
    InstrumentConfirmation,
    InstrumentDimension,
    InstrumentIndicator,
    InstrumentItem,
    InstrumentProvenance,
    InstrumentVariable,
    ItemColumnMapping,
    ScoringRule,
)
from app.modules.research.instrument.repository import (
    InstrumentConflict,
    InstrumentNotFound,
    InstrumentRepository,
    InstrumentValidationError,
)
from app.modules.research.methodology.models import MethodologyReview
from app.modules.research.methodology.repository import MethodologyRepository
from app.modules.research.projects.use_cases import ProjectNotFound, ProjectService


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class InstrumentService:
    def __init__(
        self,
        repository: InstrumentRepository,
        projects: ProjectService,
        documents: DocumentService,
        methodology: MethodologyRepository,
        datasets: DatasetService,
    ):
        self.repository = repository
        self.projects = projects
        self.documents = documents
        self.methodology = methodology
        self.datasets = datasets

    def _require_project(self, project_id: UUID) -> None:
        try:
            self.projects.get(project_id)
        except ProjectNotFound as exc:
            raise InstrumentNotFound(f"El proyecto '{project_id}' no existe.") from exc

    def _review_hash(self, review: MethodologyReview) -> str:
        return _digest(review.content.model_dump_json().encode())

    def _dataset_hash(self, project_id: UUID, dataset: Dataset) -> str:
        metadata = dataset.model_dump_json(exclude={"active"}).encode()
        raw_bytes = self.datasets.read(project_id, dataset.id)
        return _digest(metadata + raw_bytes)

    def create_draft(
        self,
        project_id: UUID,
        variables: list[InstrumentVariable],
        dimensions: list[InstrumentDimension],
        indicators: list[InstrumentIndicator],
        items: list[InstrumentItem],
        scoring_rules: list[ScoringRule] | None = None,
        provenance: InstrumentProvenance | None = None,
    ) -> InstrumentContext:
        self._require_project(project_id)
        now = datetime.now(UTC)
        instrument_id = uuid4()

        context = InstrumentContext(
            schema_version="1.0.0",
            instrument_id=instrument_id,
            project_id=project_id,
            version=0,
            status="draft",
            created_at=now,
            updated_at=now,
            provenance=provenance,
            confirmation=InstrumentConfirmation(state="pending"),
            variables=variables,
            dimensions=dimensions,
            indicators=indicators,
            items=items,
            scoring_rules=scoring_rules or [],
            dataset_mapping=None,
        )
        return self.repository.create(context)

    def get(
        self,
        project_id: UUID,
        instrument_id: UUID,
        version: int | None = None,
    ) -> InstrumentContext:
        self._require_project(project_id)
        instrument = self.repository.get(project_id, instrument_id, version=version)
        if instrument is None or instrument.project_id != project_id:
            raise InstrumentNotFound(
                f"El instrumento '{instrument_id}' no existe o no pertenece a este proyecto."
            )
        return instrument

    def list(self, project_id: UUID) -> list[InstrumentContext]:
        self._require_project(project_id)
        return self.repository.list(project_id)

    def get_history(self, project_id: UUID, instrument_id: UUID) -> list[InstrumentContext]:
        self._require_project(project_id)
        # Verifica que el instrumento exista en el proyecto
        self.get(project_id, instrument_id)
        return self.repository.get_history(project_id, instrument_id)

    def update_draft(
        self,
        project_id: UUID,
        instrument_id: UUID,
        expected_version: int,
        variables: list[InstrumentVariable] | None = None,
        dimensions: list[InstrumentDimension] | None = None,
        indicators: list[InstrumentIndicator] | None = None,
        items: list[InstrumentItem] | None = None,
        scoring_rules: list[ScoringRule] | None = None,
    ) -> InstrumentContext:
        self._require_project(project_id)
        current = self.get(project_id, instrument_id)

        # Si el instrumento ya está confirmado y revisado, no se sobrescribe destructivamente
        # El cambio genera una nueva versión en estado 'draft'
        now = datetime.now(UTC)
        updates = {
            "updated_at": now,
            "status": "draft",
            "confirmation": InstrumentConfirmation(state="pending"),
        }
        if variables is not None:
            updates["variables"] = variables
        if dimensions is not None:
            updates["dimensions"] = dimensions
        if indicators is not None:
            updates["indicators"] = indicators
        if items is not None:
            updates["items"] = items
        if scoring_rules is not None:
            updates["scoring_rules"] = scoring_rules

        # Si había mapeo de dataset y cambiaron ítems, el mapeo debe pasar a stale o actualizarse
        if current.dataset_mapping is not None and items is not None:
            new_item_ids = {it.item_id for it in items}
            mapped_item_ids = {m.item_id for m in current.dataset_mapping.item_columns}
            if new_item_ids != mapped_item_ids:
                updates["dataset_mapping"] = current.dataset_mapping.model_copy(
                    update={
                        "status": "stale",
                        "confirmation": InstrumentConfirmation(state="pending"),
                    }
                )

        updated_context = InstrumentContext.model_validate(current.model_dump() | updates)
        return self.repository.update(updated_context, expected_version)

    def link_methodology(
        self,
        project_id: UUID,
        instrument_id: UUID,
        expected_version: int,
        document_id: UUID,
        source_kind: str = "document",
    ) -> InstrumentContext:
        self._require_project(project_id)
        current = self.get(project_id, instrument_id)

        doc = next((d for d in self.documents.list(project_id) if d.id == document_id), None)
        if doc is None:
            raise InstrumentValidationError(
                f"El documento '{document_id}' no pertenece al proyecto."
            )

        review = self.methodology.get_review(project_id, document_id)
        if review is None or review.review_status != "reviewed" or review.reviewed_at is None:
            raise InstrumentValidationError(
                "La revisión metodológica asociada debe estar confirmada por un revisor humano."
            )

        review_hash = self._review_hash(review)

        source_doc_hash = None
        if source_kind == "document":
            doc_bytes = self.documents.repository.read(project_id, document_id)
            source_doc_hash = _digest(doc_bytes)

        # Validar variables vinculadas si declaran methodology_variable_id
        methodology_var_ids = {v.id for v in review.content.variables}
        for var in current.variables:
            if (
                var.methodology_variable_id
                and var.methodology_variable_id not in methodology_var_ids
            ):
                raise InstrumentValidationError(
                    f"La variable '{var.name}' referencia un methodology_variable_id "
                    f"({var.methodology_variable_id}) inexistente en la metodología confirmada."
                )

        provenance = InstrumentProvenance(
            source_kind=source_kind,
            source_document_id=document_id if source_kind == "document" else None,
            source_document_hash=source_doc_hash if source_kind == "document" else None,
            methodology_review_id=document_id,
            methodology_review_version=review.version,
            methodology_review_hash=review_hash,
        )

        now = datetime.now(UTC)
        updated_inst = current.model_copy(
            update={
                "provenance": provenance,
                "updated_at": now,
            }
        )
        return self.repository.update(updated_inst, expected_version)

    def set_mapping(
        self,
        project_id: UUID,
        instrument_id: UUID,
        expected_version: int,
        dataset_id: UUID,
        item_columns: list[ItemColumnMapping],
    ) -> InstrumentContext:
        self._require_project(project_id)
        current = self.get(project_id, instrument_id)

        try:
            dataset = self.datasets.get(project_id, dataset_id)
        except DatasetNotFound as exc:
            raise InstrumentValidationError(
                f"El dataset '{dataset_id}' no pertenece a este proyecto."
            ) from exc

        # Validar existencia exacta de columnas
        dataset_col_set = set(dataset.columns)
        for ic in item_columns:
            if ic.column_name not in dataset_col_set:
                raise InstrumentValidationError(
                    f"La columna '{ic.column_name}' no existe en el dataset seleccionado."
                )

        # Validar que los item_id existan en el instrumento
        inst_item_ids = {it.item_id for it in current.items}
        for ic in item_columns:
            if ic.item_id not in inst_item_ids:
                raise InstrumentValidationError(
                    f"El ítem '{ic.item_id}' no pertenece a este instrumento."
                )

        dataset_hash = self._dataset_hash(project_id, dataset)

        mapping = DatasetMapping(
            dataset_id=dataset_id,
            dataset_hash=dataset_hash,
            instrument_version=expected_version,
            item_columns=item_columns,
            status="draft",
            confirmation=InstrumentConfirmation(state="pending"),
        )

        now = datetime.now(UTC)
        updated_inst = current.model_copy(
            update={
                "dataset_mapping": mapping,
                "updated_at": now,
            }
        )
        return self.repository.update(updated_inst, expected_version)

    def confirm_mapping(
        self,
        project_id: UUID,
        instrument_id: UUID,
        expected_version: int,
        confirmer_ref: str,
    ) -> InstrumentContext:
        self._require_project(project_id)
        current = self.get(project_id, instrument_id)

        if current.dataset_mapping is None:
            raise InstrumentValidationError(
                "No existe un mapeo de datos configurado para confirmar."
            )

        # Validar que cubra el 100% de los ítems
        inst_item_ids = {it.item_id for it in current.items}
        mapped_item_ids = {m.item_id for m in current.dataset_mapping.item_columns}
        if inst_item_ids != mapped_item_ids:
            missing = inst_item_ids - mapped_item_ids
            raise InstrumentValidationError(
                f"El mapeo debe cubrir el 100% de los ítems. Faltan {len(missing)} ítems."
            )

        # Validar que el dataset siga existiendo y vigente
        dataset = self.datasets.get(project_id, current.dataset_mapping.dataset_id)
        current_ds_hash = self._dataset_hash(project_id, dataset)
        if current_ds_hash != current.dataset_mapping.dataset_hash:
            raise InstrumentConflict(
                "El dataset ha cambiado desde que se configuró el mapeo. Recalcula el mapeo."
            )

        now = datetime.now(UTC)
        confirmed_confirmation = InstrumentConfirmation(
            state="confirmed",
            confirmed_at=now,
            confirmer_ref=confirmer_ref,
        )
        confirmed_mapping = current.dataset_mapping.model_copy(
            update={
                "status": "confirmed",
                "confirmation": confirmed_confirmation,
            }
        )

        updated_inst = current.model_copy(
            update={
                "dataset_mapping": confirmed_mapping,
                "updated_at": now,
            }
        )
        return self.repository.update(updated_inst, expected_version)

    def confirm_instrument(
        self,
        project_id: UUID,
        instrument_id: UUID,
        expected_version: int,
        confirmer_ref: str,
    ) -> InstrumentContext:
        self._require_project(project_id)
        current = self.get(project_id, instrument_id)

        if current.provenance is None:
            raise InstrumentValidationError(
                "El instrumento requiere procedencia metodológica confirmada antes "
                "de ser confirmado."
            )

        # Validar vigencia de la metodología
        is_stale_flag, reasons = self.check_stale(project_id, instrument_id)
        if is_stale_flag:
            raise InstrumentConflict(
                f"El instrumento está desactualizado respecto a sus fuentes: {', '.join(reasons)}"
            )

        # Confirmar todas las reglas de puntuación si no lo estaban
        confirmed_rules = [
            rule.model_copy(update={"confirmed": True}) for rule in current.scoring_rules
        ]

        now = datetime.now(UTC)
        confirmed_confirmation = InstrumentConfirmation(
            state="confirmed",
            confirmed_at=now,
            confirmer_ref=confirmer_ref,
        )

        # Construir y validar el contexto confirmado
        dumped = current.model_dump()
        dumped.update(
            {
                "status": "reviewed",
                "confirmation": confirmed_confirmation.model_dump(),
                "scoring_rules": [r.model_dump() for r in confirmed_rules],
                "updated_at": now.isoformat(),
            }
        )
        confirmed_context = InstrumentContext.model_validate(dumped)
        return self.repository.update(confirmed_context, expected_version)

    def check_stale(
        self,
        project_id: UUID,
        instrument_id: UUID,
    ) -> tuple[bool, list[str]]:
        self._require_project(project_id)
        current = self.get(project_id, instrument_id)
        reasons = []

        if current.provenance is not None:
            review = self.methodology.get_review(
                project_id, current.provenance.methodology_review_id
            )
            if review is None or review.review_status != "reviewed":
                reasons.append("La revisión metodológica asociada ya no está confirmada.")
            else:
                cur_hash = self._review_hash(review)
                if (
                    review.version != current.provenance.methodology_review_version
                    or cur_hash != current.provenance.methodology_review_hash
                ):
                    reasons.append(
                        "La metodología ha cambiado desde que se vinculó el instrumento."
                    )

        if current.dataset_mapping is not None:
            try:
                dataset = self.datasets.get(project_id, current.dataset_mapping.dataset_id)
                cur_ds_hash = self._dataset_hash(project_id, dataset)
                if cur_ds_hash != current.dataset_mapping.dataset_hash:
                    reasons.append("El dataset vinculado ha sido modificado o reemplazado.")
            except DatasetNotFound:
                reasons.append("El dataset vinculado ya no existe en el proyecto.")

        return (len(reasons) > 0, reasons)
