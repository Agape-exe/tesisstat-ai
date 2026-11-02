"""Human methodology review; the AI draft and its citations remain immutable."""

from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException
from pydantic import BaseModel

from app.modules.research.methodology.models import (
    MethodologyReview,
    ReviewContent,
    ReviewFinding,
    ReviewUpdate,
)
from app.modules.research.methodology.repository import MethodologyRepository
from app.modules.research.methodology.service import MethodologyService

ROLES = {"independent", "dependent", "covariate", "descriptive", "unknown"}
SCALES = {"nominal", "ordinal", "interval", "ratio", "unknown"}
ESSENTIAL = {"title", "general_objective", "research_design"}


def paths(value: BaseModel, prefix: str = ""):
    for key in type(value).model_fields:
        item = getattr(value, key)
        path = f"{prefix}.{key}".lstrip(".")
        if isinstance(item, ReviewFinding):
            yield path, item
        elif isinstance(item, list):
            for index, child in enumerate(item):
                if isinstance(child, ReviewFinding):
                    yield f"{path}.{index}", child
                elif isinstance(child, BaseModel):
                    yield from paths(child, f"{path}.{index}")


def pending(content: ReviewContent) -> list[str]:
    result = [path for path, item in paths(content) if item.value is None or not item.value.strip()]
    for field in (
        "specific_objectives",
        "specific_hypotheses",
        "variables",
        "additional_methodology",
    ):
        if not getattr(content, field):
            result.append(field)
    for index, variable in enumerate(content.variables):
        for field in ("dimensions", "indicators", "instrument_items"):
            if not getattr(variable, field):
                result.append(f"variables.{index}.{field}")
    return result


def validate_update(content: ReviewContent, previous: ReviewContent) -> None:
    old = dict(paths(previous))
    old_variables = {variable.id: variable for variable in previous.variables}
    ids = [variable.id for variable in content.variables]
    if len(ids) != len(set(ids)):
        raise HTTPException(422, {"variables": "Los identificadores deben ser únicos."})
    for path, item in paths(content):
        if item.value is not None and not item.value.strip():
            raise HTTPException(422, {path: "Escribe un valor o déjalo desconocido."})
        if item.kind in ("quotation", "inference"):
            candidates = [old.get(path)]
            parts = path.split(".")
            if len(parts) == 2 and parts[1].isdigit():
                candidates = getattr(previous, parts[0], [])
            elif len(parts) >= 3 and parts[0] == "variables":
                variable = content.variables[int(parts[1])]
                prior = old_variables.get(variable.id)
                if prior:
                    candidates = (
                        [getattr(prior, parts[2])]
                        if len(parts) == 3
                        else getattr(prior, parts[2], [])
                    )
            if item not in candidates:
                raise HTTPException(422, {path: "Las citas de IA no se pueden modificar."})
        if (
            path.endswith(".role")
            and item.kind == "manual"
            and item.value
            and item.value not in ROLES
        ):
            raise HTTPException(422, {path: "Selecciona un rol válido."})
        if (
            path.endswith(".measurement_scale")
            and item.kind == "manual"
            and item.value
            and item.value not in SCALES
        ):
            raise HTTPException(422, {path: "Selecciona una escala válida."})


class ReviewService:
    def __init__(self, methodology: MethodologyService, repository: MethodologyRepository):
        self.methodology = methodology
        self.repository = repository

    def get(self, project_id: UUID, document_id: UUID) -> MethodologyReview | None:
        self.methodology.get(project_id, document_id)
        return self.repository.get_review(project_id, document_id)

    def create(self, project_id: UUID, document_id: UUID) -> MethodologyReview:
        state = self.methodology.get(project_id, document_id)
        if state.status == "processing":
            raise HTTPException(409, "Espera a que termine el análisis en curso.")
        if self.repository.get_review(project_id, document_id):
            raise HTTPException(409, "La metodología editable ya existe.")
        if state.draft:
            raw = state.draft.content.model_dump()
            raw.pop("warnings", None)
            raw.pop("questions", None)
            content = ReviewContent.model_validate(raw)
            origin = "ai"
        else:
            content = ReviewContent()
            origin = "manual"
        review = MethodologyReview(
            project_id=project_id,
            document_id=document_id,
            origin=origin,
            content=content,
            pending_fields=pending(content),
            updated_at=datetime.now(UTC),
        )
        if not self.repository.save_review(review, None):
            raise HTTPException(409, "La metodología editable ya existe.")
        return review

    def save(self, project_id: UUID, document_id: UUID, update: ReviewUpdate) -> MethodologyReview:
        review = self.get(project_id, document_id)
        if review is None:
            raise HTTPException(404, "Primero crea la metodología editable.")
        if update.version != review.version:
            raise HTTPException(409, "Otra edición fue guardada. Recarga antes de continuar.")
        validate_update(update.content, review.content)
        review.content = update.content
        review.pending_fields = pending(update.content)
        review.review_status = "unreviewed"
        review.reviewed_at = None
        review.version += 1
        review.updated_at = datetime.now(UTC)
        if not self.repository.save_review(review, update.version):
            raise HTTPException(409, "Otra edición fue guardada. Recarga antes de continuar.")
        return review

    def confirm(self, project_id: UUID, document_id: UUID, version: int) -> MethodologyReview:
        review = self.get(project_id, document_id)
        if review is None:
            raise HTTPException(404, "Primero crea la metodología editable.")
        if version != review.version:
            raise HTTPException(409, "Otra edición fue guardada. Recarga antes de continuar.")
        missing = [field for field in ESSENTIAL if field in review.pending_fields]
        if not review.content.variables or any(
            not item.name.value for item in review.content.variables
        ):
            missing.append("variables")
        if missing:
            raise HTTPException(422, {"pending_fields": sorted(missing)})
        review.review_status = "reviewed"
        review.reviewed_at = datetime.now(UTC)
        review.updated_at = review.reviewed_at
        review.version += 1
        if not self.repository.save_review(review, version):
            raise HTTPException(409, "Otra edición fue guardada. Recarga antes de continuar.")
        return review

    def reviewed_content(self, project_id: UUID, document_id: UUID) -> ReviewContent | None:
        """Read interface for a future ResearchPackage use case; no package is created here."""
        review = self.get(project_id, document_id)
        return review.content if review and review.review_status == "reviewed" else None
