from datetime import UTC, datetime
from uuid import uuid4

from pydantic import ValidationError

from app.modules.research.data_workspace.service import fail
from app.modules.research.intents.repository import EvidenceStore
from app.modules.research.sources.repository import missing
from app.shared.analysis_v2 import AnalysisIntentV2, Confirmation, Fact, Provenance

FACTS = {
    "reliability_group",
    "question",
    "observations",
    "observational_unit",
    "identification",
    "comparison_notes",
    "linkage",
}


class IntentService:
    def __init__(self, workspace, repository: EvidenceStore, contexts=None):
        self.contexts = contexts
        self.workspace = workspace
        self.repository = repository

    def get(self, project_id, intent_id):
        self.workspace.sources.require(project_id)
        value = self.repository.get(project_id, "intent", intent_id)
        if not value:
            missing()
        return AnalysisIntentV2.model_validate(value)

    def list(self, project_id):
        self.workspace.sources.require(project_id)
        return [
            AnalysisIntentV2.model_validate(v) for v in self.repository.all(project_id, "intent")
        ]

    def revisions(self, project_id, intent_id):
        self.get(project_id, intent_id)
        return self.repository.revisions(project_id, "intent", intent_id)

    def save(self, project_id, patch, intent_id=None):
        self.workspace.sources.require(project_id)
        with self.repository.transaction() as db:
            now = datetime.now(UTC)
            current = (
                self.get(project_id, intent_id)
                if intent_id
                else AnalysisIntentV2(
                    id=str(uuid4()),
                    project_id=project_id,
                    revision=1,
                    created_at=now,
                    updated_at=now,
                )
            )
            if intent_id:
                current.revision += 1
            current.updated_at = now
            current.confirmation = None
            # Any edited intention needs its analysis-specific relation reviewed anew.
            for field in FACTS:
                getattr(current, field).confirmation = None
            for condition in type(current.conditions).model_fields:
                getattr(current.conditions, condition).confirmation = None
            for field in patch.changes.model_fields_set:
                value = getattr(patch.changes, field)
                if field == "conditions":
                    if value is None:
                        current.conditions = type(current.conditions)()
                    else:
                        for name in value.model_fields_set:
                            raw = getattr(value, name)
                            setattr(
                                current.conditions,
                                name,
                                Fact(value=raw or None, provenance=Provenance(kind="manual")),
                            )
                elif field in FACTS:
                    setattr(
                        current,
                        field,
                        Fact(value=value or None, provenance=Provenance(kind="manual")),
                    )
                else:
                    if value is None and field in {"variable_ids", "roles"}:
                        value = []
                    setattr(current, field, value)
            try:
                current = AnalysisIntentV2.model_validate(current.model_dump())
            except ValidationError:
                fail("Revisa el tipo, variables y propósito de este análisis.")
            context = self.contexts.get(project_id) if self.contexts else None
            if current.objective_id and (
                not context
                or current.objective_id not in {o.id for o in context.specific_objectives}
            ):
                fail("El objetivo debe existir en el Contexto de este proyecto.")
            if current.hypothesis_id and (
                not context or current.hypothesis_id not in {h.id for h in context.hypotheses}
            ):
                fail("La hipótesis debe existir en el Contexto de este proyecto.")
            if current.dataset_id:
                dataset, _ = self.workspace.read_table(project_id, current.dataset_id)
                dictionary = self.workspace.dictionary(project_id, dataset.id, dataset)
                selected = {v.id: v for v in dictionary.variables if v.id in current.variable_ids}
                if set(selected) != set(current.variable_ids):
                    fail("Selecciona variables del diccionario de esta tabla.")
                columns = {c for v in selected.values() for c in v.column_ids}
                if current.group_column_id and current.group_column_id not in columns:
                    fail("Incluye la variable de grupo entre las seleccionadas.")
                if current.paired_columns and not {
                    current.paired_columns.before_column_id,
                    current.paired_columns.after_column_id,
                }.issubset(columns):
                    fail("Selecciona ambas mediciones de esta tabla para revisar pares.")
                if current.identifier_column_id and current.identifier_column_id not in {
                    c.id for c in dataset.columns
                }:
                    fail("El identificador debe pertenecer a esta tabla.")
            elif current.variable_ids or current.group_column_id or current.paired_columns:
                fail("Elige primero la tabla de estas variables.")
            if patch.confirm:
                if current.kind == "unknown" or current.estimand == "unknown":
                    fail("Puedes guardar un borrador; indica el propósito antes de confirmarlo.")
                confirmation = Confirmation(
                    actor_ref=self.workspace.sources.actor_ref,
                    confirmed_at=now,
                    revision=current.revision,
                )
                current.confirmation = confirmation
                for field in FACTS:
                    fact = getattr(current, field)
                    if fact.value not in (None, "", "unknown"):
                        fact.confirmation = confirmation
                for name in type(current.conditions).model_fields:
                    fact = getattr(current.conditions, name)
                    if fact.value not in (None, "", "unknown"):
                        fact.confirmation = confirmation
            self.repository.put(
                db,
                project_id,
                "intent",
                current.id,
                current.model_dump(mode="json"),
                patch.expected_revision,
            )
        return current
