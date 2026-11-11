"""Server selected C2-C6 evidence. No query text can select or authorize a source."""

import hashlib
import json
from uuid import UUID

from app.modules.research.context.repository import ContextError
from app.modules.research.context.use_cases import context_facts
from app.modules.research.data_workspace.service import ref
from app.orchestration.analysis_v2_service import reference
from app.shared.analysis_v2 import SourceRef, canonical_hash
from app.shared.tutor_v2 import TutorActionV2, TutorContextV2


def digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=False, default=str).encode()
    ).hexdigest()


HELP = {
    "home": "Puedes comenzar por Contexto o cargar una tabla en Datos. El documento y las "
    "hipótesis son opcionales; describir datos no los requiere.",
    "context": "Guarda lo que sabes de la pregunta y objetivo. Confirma solo lo revisado. "
    "Qué representa cada fila se describe para cada tabla en Datos.",
    "data": "Selecciona una tabla, revisa sus variables y escalas y calcula su perfil. "
    "Preparar o combinar es opcional y requiere revisión explícita.",
    "analysis": "Selecciona una intención y su tabla. Revisa diagnósticos y propuesta; "
    "autorizar datos, aprobar la propuesta y ejecutar son acciones separadas.",
    "results": "Selecciona un resultado guardado. Comprueba casos, método, incertidumbre y "
    "limitaciones. Un resultado no completa toda la investigación.",
}


class TutorContextBuilder:
    def __init__(self, analysis, context_service):
        self.analysis, self.contexts = analysis, context_service
        self.workspace, self.intents = analysis.workspace, analysis.intents

    def build(self, project, selection):
        self.workspace.sources.require(project)
        context = self.contexts.get(project)
        refs, historical, warnings, pending, data = [], [], [], [], []
        project_value = self.contexts.projects.get(UUID(project))
        refs.append(
            SourceRef(
                kind="project",
                id=project,
                revision=1,
                hash=digest(project_value.model_dump(mode="json")),
            )
        )
        actions = [
            TutorActionV2(kind="open", label=label, destination=destination)
            for destination, label in (
                ("context", "Revisar contexto"),
                ("datasets", "Cargar o revisar datos"),
                ("analysis", "Revisar análisis"),
                ("results", "Comprender resultados"),
            )
        ]
        confirmed = {
            path: str(f.value)
            for path, f in context_facts(context).items()
            if f.confirmation and f.value is not None and path != "/observations"
        }
        if context.revision:
            refs.append(
                SourceRef(
                    kind="context",
                    id=project,
                    revision=context.revision,
                    hash=canonical_hash(context),
                )
            )
        pending += [q.question for q in context.pending_questions]
        intent = plan = result = None
        if selection.result_id:
            result, plan = self.analysis.result_with_plan(project, selection.result_id)
        if selection.plan_id:
            selected = self.analysis.get(project, selection.plan_id)
            if plan and plan.id != selected.id:
                raise ContextError(
                    "selection_mismatch", "El resultado no pertenece a esa propuesta."
                )
            plan = selected
        if plan:
            intent = self.intents.get(project, plan.intent_id)
        if selection.intent_id:
            selected = self.intents.get(project, selection.intent_id)
            if intent and intent.id != selected.id:
                raise ContextError("selection_mismatch", "Selecciona recursos del mismo análisis.")
            intent = selected
        dataset_id = selection.dataset_id or (intent.dataset_id if intent else None)
        if intent and selection.dataset_id and intent.dataset_id != selection.dataset_id:
            raise ContextError("selection_mismatch", "La tabla no corresponde a esta intención.")
        historical_selection = bool(plan and plan.validity == "stale")
        if historical_selection:
            dataset_id = None
            warnings.append(
                "Se explican referencias históricas sin volver a leer sus observaciones."
            )
            if result:
                data.append({"rows": result.case_counts.total, "kind": "historical"})
        datasets = self.workspace.datasets(project)
        # Inventory contributes to the fingerprint without silently selecting a last item.
        inventory = [ref("dataset", d).model_dump(mode="json") for d in datasets]
        inventory += [
            reference("intent", i).model_dump(mode="json") for i in self.intents.list(project)
        ]
        if dataset_id:
            ds, _ = self.workspace.read_table(project, dataset_id)
            refs += [*ds.source_refs, ref("dataset", ds)]
            dictionary = self.workspace.dictionary(project, ds.id, ds)
            if dictionary.revision:
                refs.append(ref("dictionary", dictionary))
            selected_ids = set(intent.variable_ids) if intent else set()
            variables = [
                v for v in dictionary.variables if not selected_ids or v.id in selected_ids
            ]
            for n, variable in enumerate(variables[:30]):
                data.append(
                    {
                        "variable": f"Variable {n + 1}",
                        "scale": variable.measurement_scale.value,
                        "scale_confirmed": bool(variable.measurement_scale.confirmation),
                        "identifier": variable.identifier_confirmed.value is True,
                    }
                )
            data.insert(0, {"rows": ds.row_count, "columns": len(ds.columns), "kind": ds.kind})
            if len(variables) > 30:
                warnings.append("Resumen limitado a treinta variables; selecciona un análisis.")
            try:
                profile = self.workspace.profile(project, ds.id)
                profile_ref = ref("profile", profile)
                (refs if profile.state == "current" else historical).append(profile_ref)
                data[0]["profile_state"] = profile.state
            except ContextError as exc:
                if exc.status not in {404, 409}:
                    raise
                data[0]["profile_state"] = "missing" if exc.status == 404 else "stale"
                pending.append("Calcula un perfil vigente para la tabla seleccionada en Datos.")
        elif datasets and not historical_selection:
            pending.append("Selecciona la tabla pertinente; no se elige la última automáticamente.")
        summary = {}
        if intent:
            refs.append(reference("intent", intent))
            summary = {
                "id": intent.id,
                "kind": intent.kind,
                "estimand": intent.estimand,
                "revision": intent.revision,
                "confirmed": bool(intent.confirmation),
                "observations": intent.observations.value,
                "observations_confirmed": bool(intent.observations.confirmation),
            }
            for field in (
                "instrument_id",
                "instrument_revision",
                "mapping_revision",
                "scoring_rule_id",
            ):
                value = getattr(intent, field, None)
                if value is not None:
                    summary[field] = value
            if intent.instrument_id and not historical_selection:
                instruments = self.analysis.diagnostics.instruments
                instrument = instruments.get(project, intent.instrument_id)
                instrument_ref = SourceRef(
                    kind="instrument",
                    id=instrument.instrument_id,
                    revision=instrument.revision,
                    hash=canonical_hash(instrument),
                )
                (refs if instrument.status == "reviewed" else historical).append(instrument_ref)
                summary["instrument_state"] = instrument.status
                summary["item_count"] = len(instrument.items)
                summary["reverse_item_count"] = sum(i.reverse_scored for i in instrument.items)
                try:
                    mapping = instruments.mapping(project, intent.instrument_id)
                    mapping_ref = reference("mapping", mapping)
                    (refs if mapping.status == "confirmed" else historical).append(mapping_ref)
                    summary["mapping_state"] = mapping.status
                except ContextError as exc:
                    if exc.status not in {404, 409}:
                        raise
                    pending.append("Revisa la correspondencia del instrumento seleccionado.")
                rule = next(
                    (
                        r
                        for r in instrument.scoring_rules
                        if str(r.scoring_rule_id) == intent.scoring_rule_id
                    ),
                    None,
                )
                if rule:
                    summary["aggregation"] = rule.aggregation
                    summary["missing_policy"] = rule.missing_policy
            for value in self.analysis.store.all(project, "diagnostic"):
                if value["intent_id"] != intent.id:
                    continue
                diagnostic = self.analysis.diagnostics.get(project, value["id"])
                (refs if diagnostic.state == "current" else historical).append(
                    reference("diagnostic", diagnostic)
                )
            actions += [
                TutorActionV2(
                    kind=kind,
                    resource_id=intent.id,
                    label=label,
                    destination="analysis",
                    scope=f"Intención {intent.id}, revisión {intent.revision}; "
                    f"tabla {intent.dataset_id}. " + scope,
                )
                for kind, label, scope in (
                    (
                        "request_diagnostic",
                        "Revisar alcance y solicitar diagnósticos",
                        "Elige las comprobaciones antes de calcular.",
                    ),
                    (
                        "request_proposal",
                        "Revisar alcance y solicitar propuesta",
                        "Usa el selector C4–C5; no aprueba ni ejecuta.",
                    ),
                )
            ]
        elif selection.stage in {"analysis", "results"}:
            pending.append(
                "Selecciona el análisis que quieres comprender; no se mezclan intenciones."
            )
        plan_ref = result_ref = None
        if plan:
            plan_ref = reference("plan", plan)
            (refs if plan.validity == "current" else historical).append(plan_ref)
            pending += [q.question for q in plan.pending_questions]
            summary["plan_status"] = plan.status
            summary["plan_validity"] = plan.validity
            summary["execution_status"] = plan.execution_status
            summary["technique"] = plan.technique
            for r in plan.evidence_refs:
                (refs if plan.validity == "current" else historical).append(r)
        if result:
            result_ref = reference("result", result)
            (refs if result.validity == "current" else historical).append(result_ref)
            summary["result_status"] = result.status
            summary["result_validity"] = result.validity
            if result.validity == "stale":
                warnings.append(
                    "El resultado es histórico desactualizado; "
                    "sus cifras no acreditan las fuentes actuales."
                )
            for r in result.source_refs:
                (refs if result.validity == "current" else historical).append(r)
        elif selection.stage == "results":
            pending.append(
                "Elige un resultado concreto; sin él solo se explican conceptos y próximos pasos."
            )
        refs = list({(r.kind, r.id, r.revision, r.hash): r for r in refs}.values())
        historical = list({(r.kind, r.id, r.revision, r.hash): r for r in historical}.values())
        value = TutorContextV2(
            project_id=project,
            stage=selection.stage,
            context_fingerprint="0" * 64,
            source_refs=refs,
            confirmed_summary=confirmed,
            pending_questions=list(dict.fromkeys(pending)),
            data_summary=data,
            intent_summary=summary,
            current_plan_ref=plan_ref if plan and plan.validity == "current" else None,
            current_result_ref=result_ref if result and result.validity == "current" else None,
            historical_refs=historical,
            allowed_actions=actions,
            warnings=warnings,
        )
        value.context_fingerprint = digest(
            {
                "context": value.model_dump(mode="json"),
                "selection": selection.model_dump(mode="json"),
                "inventory": inventory,
            }
        )
        return value, result
