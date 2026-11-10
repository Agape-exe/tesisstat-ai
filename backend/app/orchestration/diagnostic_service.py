"""Resolve server evidence, calculate purely, revalidate under DB lock before publish."""

from datetime import UTC, datetime
from uuid import uuid4

from app.modules.research.context.repository import ContextError
from app.modules.research.data_workspace.service import fail, ref
from app.modules.research.sources.repository import missing
from app.modules.statistics.diagnostics import ENGINE, VERSION, evaluate
from app.shared.analysis_v2 import SourceRef, canonical_hash
from app.shared.diagnostics_v2 import DiagnosticScopeV2, DiagnosticV2


class DiagnosticService:
    def __init__(self, intents, workspace, store):
        self.intents, self.workspace, self.store = intents, workspace, store

    def resolve(self, project_id, intent_id):
        intent = self.intents.get(project_id, intent_id)
        if not intent.dataset_id or not intent.variable_ids:
            fail("Guarda la tabla y al menos una variable antes de solicitar diagnósticos.")
        dataset, rows = self.workspace.read_table(project_id, intent.dataset_id)
        dictionary = self.workspace.dictionary(project_id, dataset.id, dataset)
        if canonical_hash(dictionary) != dictionary.hash:
            fail("El diccionario almacenado no coincide con su hash.", "storage_unavailable", 503)
        if dictionary.revision == 0:
            fail(
                "Guarda la revisión de variables en Datos antes de solicitar diagnósticos.",
                "source_stale",
                409,
            )
        profile = self.workspace.profile(project_id, dataset.id)
        if profile.state != "current":
            fail(
                "Actualiza el perfil de la tabla antes de solicitar diagnósticos.",
                "source_stale",
                409,
            )
        if canonical_hash(profile) != profile.hash:
            fail("El perfil almacenado no coincide con su hash.", "storage_unavailable", 503)
        selected = {v.id: v for v in dictionary.variables if v.id in intent.variable_ids}
        if set(selected) != set(intent.variable_ids) or any(
            not v.column_ids for v in selected.values()
        ):
            fail("Cambió el vínculo de las variables; revisa la intención.", "source_stale", 409)
        selected_columns = {c for v in selected.values() for c in v.column_ids}
        required = {intent.group_column_id} if intent.group_column_id else set()
        if intent.paired_columns:
            required.update(
                [intent.paired_columns.before_column_id, intent.paired_columns.after_column_id]
            )
        if not required.issubset(selected_columns):
            fail(
                "Cambió el vínculo de grupos o mediciones; revisa la intención.",
                "source_stale",
                409,
            )
        refs = [
            *dataset.source_refs,
            ref("dataset", dataset),
            ref("dictionary", dictionary),
            ref("profile", profile),
            SourceRef(
                kind="intent", id=intent.id, revision=intent.revision, hash=canonical_hash(intent)
            ),
        ]
        # All references are reconstructed from server resources, never supplied by caller.
        refs = list({(r.kind, r.id): r for r in refs}.values())
        return intent, dataset, dictionary, rows, refs

    def create(self, project_id, request):
        intent, dataset, dictionary, rows, refs = self.resolve(project_id, request.intent_id)
        if (
            intent.revision != request.intent_revision
            or dataset.id != request.dataset_id
            or dataset.revision != request.dataset_revision
        ):
            fail(
                "La intención o la tabla cambió. Revisa el alcance antes de calcular.",
                "source_stale",
                409,
            )
        if len(set(request.checks)) != len(request.checks):
            fail("No repitas comprobaciones.")
        profile, checks, figures, warnings = evaluate(
            intent, dataset, dictionary, rows, request.checks
        )
        result = DiagnosticV2(
            id=str(uuid4()),
            project_id=project_id,
            source_refs=refs,
            created_at=datetime.now(UTC),
            intent_id=intent.id,
            scope=DiagnosticScopeV2(
                column_ids=[
                    c
                    for v in dictionary.variables
                    if v.id in intent.variable_ids
                    for c in v.column_ids
                ],
                checks=request.checks,
                alpha=intent.alpha,
            ),
            status="completed"
            if profile.complete_case_count and any(c.status != "not_checked" for c in checks)
            else "not_calculable",
            algorithm_version=VERSION,
            engine_version=ENGINE,
            checks=checks,
            warnings=warnings,
            profile=profile,
            figures=figures,
        )
        with self.store.transaction() as db:
            # BEGIN IMMEDIATE excludes every local C2/C3/intent writer until publication.
            *_, current_refs = self.resolve(project_id, request.intent_id)
            if current_refs != refs:
                fail(
                    "Las dependencias cambiaron durante el cálculo; solicita un diagnóstico nuevo.",
                    "source_stale",
                    409,
                )
            self.store.put(
                db, project_id, "diagnostic", result.id, result.model_dump(mode="json"), 0
            )
        return result

    def get(self, project_id, diagnostic_id):
        self.workspace.sources.require(project_id)
        value = self.store.get(project_id, "diagnostic", diagnostic_id)
        if not value:
            missing()
        result = DiagnosticV2.model_validate(value)
        try:
            *_, refs = self.resolve(project_id, result.intent_id)
            if refs != result.source_refs:
                result.state, result.stale_reason = (
                    "stale",
                    "Cambió la intención, tabla, diccionario o perfil.",
                )
        except ContextError as exc:
            if exc.status not in {404, 409, 422}:
                raise
            result.state, result.stale_reason = "stale", exc.message
        return result

    def list(self, project_id, intent_id=None):
        self.workspace.sources.require(project_id)
        if intent_id:
            self.intents.get(project_id, intent_id)
        return [
            self.get(project_id, item["id"])
            for item in self.store.all(project_id, "diagnostic")
            if not intent_id or item["intent_id"] == intent_id
        ]
