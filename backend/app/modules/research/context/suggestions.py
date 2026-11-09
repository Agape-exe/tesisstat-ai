from datetime import UTC, datetime
from uuid import uuid4

from pydantic import ValidationError

from app.modules.research.context.import_models import (
    ContextSuggestion,
    SuggestionApply,
    SuggestionCreate,
)
from app.modules.research.context.import_parser import candidates, parse_response
from app.modules.research.context.repository import ContextError
from app.modules.research.context.use_cases import ContextService, derive
from app.shared.analysis_v2 import (
    Confirmation,
    ContextHypothesis,
    Fact,
    ProjectContextV2,
    Provenance,
    SpecificObjective,
)


class SuggestionService:
    def __init__(self, context: ContextService):
        self.context = context
        self.repository = context.repository

    def create(self, project_id: str, body: SuggestionCreate):
        project_id = self.context._require(project_id)
        proposal, extra = parse_response(body.response)
        suggestion = ContextSuggestion(
            id=str(uuid4()),
            project_id=project_id,
            base_revision=body.expected_revision,
            proposal=proposal,
            created_at=datetime.now(UTC),
            additional_fields=extra,
        )
        return self.repository.create_suggestion(suggestion)

    def list(self, project_id: str):
        return self.repository.list_suggestions(self.context._require(project_id))

    def get(self, project_id: str, suggestion_id: str):
        return self.repository.suggestion_operation(
            self.context._require(project_id), suggestion_id, "read"
        )

    def reject(self, project_id: str, suggestion_id: str):
        return self.repository.suggestion_operation(
            self.context._require(project_id), suggestion_id, "reject"
        )

    def apply(self, project_id: str, suggestion_id: str, body: SuggestionApply):
        def build(previous: ProjectContextV2, suggestion: ContextSuggestion):
            # Edits can correct values, never inject new local identities or server metadata.
            for name in ("specific_objectives", "hypotheses"):
                if [i.ref for i in getattr(body.proposal, name)] != [
                    i.ref for i in getattr(suggestion.proposal, name)
                ]:
                    raise ContextError(
                        "invalid_payload", "Conserva las referencias de la propuesta."
                    )
            available = candidates(body.proposal)
            selected = body.selected_fields
            if len(set(selected)) != len(selected) or any(k not in available for k in selected):
                raise ContextError("invalid_payload", "Selecciona campos presentes sin repetirlos.")
            result = previous.model_copy(deep=True)
            result.revision += 1
            result.updated_at = datetime.now(UTC)
            provenance = Provenance(
                kind="ai_suggestion", algorithm_version=f"context-import-1.0:{suggestion.id}"
            )

            def fact(value):
                return Fact(
                    value=value,
                    provenance=provenance,
                    confirmation=Confirmation(
                        actor_ref=self.context.actor_ref,
                        confirmed_at=result.updated_at,
                        revision=result.revision,
                    )
                    if body.confirm
                    else None,
                )

            refs = {}
            for objective in body.proposal.specific_objectives:
                if f"specific_objectives/{objective.ref}" not in selected:
                    continue
                if any(
                    (o.text.value or "").casefold() == objective.text.casefold()
                    for o in result.specific_objectives
                ):
                    raise ContextError(
                        "invalid_payload",
                        "El objetivo ya existe. Desmárcalo; "
                        "desvincula la hipótesis o revisa su texto.",
                    )
                item = SpecificObjective(id=str(uuid4()), text=fact(objective.text))
                refs[objective.ref] = item.id
                result.specific_objectives.append(item)
            for key in selected:
                value = available[key]
                if key.startswith("specific_objectives/"):
                    continue
                if key.startswith("hypotheses/"):
                    if value.objective_ref and value.objective_ref not in refs:
                        raise ContextError(
                            "invalid_payload",
                            "Selecciona también el objetivo vinculado "
                            "o elige Sin vínculo para esa hipótesis.",
                            fields=[key],
                        )
                    if any(
                        (h.statement.value or "").casefold() == value.statement.casefold()
                        for h in result.hypotheses
                    ):
                        raise ContextError("invalid_payload", "La hipótesis ya existe. Desmárcala.")
                    result.hypotheses.append(
                        ContextHypothesis(
                            id=str(uuid4()),
                            statement=fact(value.statement),
                            objective_id=refs.get(value.objective_ref),
                            alternative=value.alternative,
                        )
                    )
                elif key.startswith("complementary_notes/"):
                    if any(
                        (n.value or "").casefold() == value.casefold()
                        for n in result.complementary_notes
                    ):
                        raise ContextError("invalid_payload", "La nota ya existe. Desmárcala.")
                    result.complementary_notes.append(fact(value))
                else:
                    setattr(result, key, fact(value))
            try:
                validated = derive(ProjectContextV2.model_validate(result.model_dump()))
            except ValidationError as exc:
                raise ContextError(
                    "invalid_payload",
                    "La combinación supera los límites del contexto "
                    "(40 objetivos, 40 hipótesis, 20 notas). Selecciona menos elementos.",
                ) from exc
            suggestion.applied_by = self.context.actor_ref
            return validated

        return self.repository.suggestion_operation(
            self.context._require(project_id), suggestion_id, "apply", body, build
        )
