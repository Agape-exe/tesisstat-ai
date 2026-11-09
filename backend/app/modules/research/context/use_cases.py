from datetime import UTC, datetime
from uuid import UUID, uuid4

from pydantic import ValidationError

from app.modules.research.context.models import ContextPatch
from app.modules.research.context.repository import ContextError, ContextRepository
from app.modules.research.projects.use_cases import ProjectNotFound, ProjectService
from app.shared.analysis_v2 import (
    Confirmation,
    ContextHypothesis,
    Fact,
    PendingQuestion,
    ProjectContextV2,
    Provenance,
    SpecificObjective,
)


def context_facts(context: ProjectContextV2) -> dict[str, Fact]:
    facts = {
        f"/{name}": getattr(context, name)
        for name in (
            "research_question",
            "main_objective",
            "study_description",
            "data_description",
            "observational_unit",
            "sampling_notes",
            "design",
            "observations",
        )
    }
    facts.update(
        {
            f"/specific_objectives/{i}/text": o.text
            for i, o in enumerate(context.specific_objectives)
        }
    )
    facts.update(
        {f"/hypotheses/{i}/statement": h.statement for i, h in enumerate(context.hypotheses)}
    )
    facts.update(
        {f"/complementary_notes/{i}": n for i, n in enumerate(context.complementary_notes)}
    )
    return facts


def derive(context: ProjectContextV2) -> ProjectContextV2:
    """No intent is selected in C2: meaningful content is partial, never globally usable."""
    meaningful = any(f.value not in (None, "", "unknown") for f in context_facts(context).values())
    context.state = "partial" if meaningful else "empty"
    context.pending_questions = []
    if not context.research_question.value and not context.main_objective.value:
        context.pending_questions.append(
            PendingQuestion(
                code="purpose",
                field="/main_objective",
                question="¿Qué quieres comprender? Puedes explorar Datos mientras lo decides.",
                blocks="proposal",
            )
        )
    for field, question in (
        ("observational_unit", "¿Qué representa cada fila?"),
        ("observations", "¿Las filas son independientes o hay mediciones relacionadas?"),
    ):
        if getattr(context, field).value in (None, "unknown"):
            context.pending_questions.append(
                PendingQuestion(
                    code=field,
                    field=f"/{field}",
                    question=question,
                    blocks="proposal",
                )
            )
    return context


class ContextService:
    def __init__(
        self,
        projects: ProjectService,
        repository: ContextRepository,
        *,
        actor_ref: str,
    ) -> None:
        self.projects = projects
        self.repository = repository
        self.actor_ref = actor_ref

    def _require(self, project_id: str) -> str:
        try:
            project = self.projects.get(UUID(project_id))
        except (ValueError, ProjectNotFound) as exc:
            raise ContextError("resource_not_found", "No se encontró el recurso.", 404) from exc
        return str(project.id)

    def get(self, project_id: str) -> ProjectContextV2:
        project_id = self._require(project_id)
        return self.repository.get(project_id) or derive(ProjectContextV2(project_id=project_id))

    def revisions(self, project_id: str) -> list[ProjectContextV2]:
        project_id = self._require(project_id)
        return self.repository.revisions(project_id)

    def patch(self, project_id: str, patch: ContextPatch) -> ProjectContextV2:
        project_id = self._require(project_id)
        if not patch.changes.model_fields_set and not patch.confirm_fields:
            raise ContextError("invalid_payload", "Indica cambios o campos para confirmar.")

        def build(previous: ProjectContextV2) -> ProjectContextV2:
            current = previous.model_copy(deep=True)
            current.revision += 1
            current.updated_at = datetime.now(UTC)

            def manual(value, old: Fact | None = None, metadata_changed=False) -> Fact:
                value = value.strip() or None if isinstance(value, str) else value
                if old and old.value == value and not metadata_changed:
                    return old.model_copy(deep=True)
                return Fact(value=value, provenance=Provenance(kind="manual"))

            def checked_id(item_id: str | None, previous_items: dict) -> str:
                if item_id is None:
                    return str(uuid4())
                if item_id not in previous_items:
                    raise ContextError(
                        "invalid_payload", "El identificador no pertenece a esta lista."
                    )
                return item_id

            for name in patch.changes.model_fields_set:
                value = getattr(patch.changes, name)
                if name == "specific_objectives":
                    old = {o.id: o for o in previous.specific_objectives}
                    current.specific_objectives = [
                        SpecificObjective(
                            id=checked_id(o.id, old),
                            text=manual(o.text, old[o.id].text if o.id in old else None),
                        )
                        for o in value or []
                    ]
                elif name == "hypotheses":
                    old = {h.id: h for h in previous.hypotheses}
                    current.hypotheses = []
                    for h in value or []:
                        prior = old.get(h.id)
                        objective_id = (
                            h.objective_id
                            if "objective_id" in h.model_fields_set or prior is None
                            else prior.objective_id
                        )
                        alternative = (
                            h.alternative
                            if "alternative" in h.model_fields_set or prior is None
                            else prior.alternative
                        )
                        current.hypotheses.append(
                            ContextHypothesis(
                                id=checked_id(h.id, old),
                                objective_id=objective_id,
                                alternative=alternative,
                                statement=manual(
                                    h.statement,
                                    prior.statement if prior else None,
                                    prior is not None
                                    and (
                                        prior.objective_id != objective_id
                                        or prior.alternative != alternative
                                    ),
                                ),
                            )
                        )
                elif name == "complementary_notes":
                    # Preserve provenance of unchanged notes across reordering.
                    current.complementary_notes = [
                        manual(
                            note,
                            next(
                                (n for n in previous.complementary_notes if n.value == note), None
                            ),
                        )
                        for note in value or []
                    ]
                else:
                    setattr(current, name, manual(value, getattr(previous, name)))

            # Validate IDs and references before confirming; nothing is written on failure.
            current = ProjectContextV2.model_validate(current.model_dump())
            facts = context_facts(current)
            if len(set(patch.confirm_fields)) != len(patch.confirm_fields):
                raise ContextError("invalid_payload", "Hay campos repetidos para confirmar.")
            for path in patch.confirm_fields:
                fact = facts.get(path)
                if fact is None or fact.value in (None, "", "unknown"):
                    raise ContextError(
                        "invalid_payload",
                        "Solo puedes confirmar campos conocidos y presentes.",
                        fields=[path],
                    )
                fact.confirmation = Confirmation(
                    actor_ref=self.actor_ref,
                    confirmed_at=current.updated_at,
                    revision=current.revision,
                )
            return derive(current)

        try:
            return self.repository.append(project_id, patch.expected_revision, build)
        except ValidationError as exc:
            raise ContextError(
                "invalid_payload",
                "Revisa identificadores y referencias de objetivos e hipótesis.",
                fields=["/" + "/".join(str(p) for p in e["loc"]) for e in exc.errors()],
            ) from exc
