"""C4/C5 coordinator. SQLite CAS spans all local C2/C3/C4 writers.

Execution claims have a bounded lease; expired attempts become failed/interrupted on
read or retry. Publication is fenced by the claim. No volatile job is called completed.
"""

import hashlib
import json
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from app.modules.research.context.repository import ContextError
from app.modules.research.data_workspace.service import fail
from app.modules.research.sources.repository import missing
from app.modules.statistics.execution_v2 import ExecutionInputV2, execute
from app.modules.statistics.inferential import StatisticalCalculationError
from app.modules.statistics.planning_v2 import (
    METHODS,
    VERSIONS,
    PlanningInputV2,
    case_counts,
    select,
)
from app.shared.analysis_v2 import (
    AnalysisSnapshotV2,
    Confirmation,
    SnapshotVariableV2,
    SourceRef,
    canonical_hash,
    snapshot_fingerprint,
)
from app.shared.plans_v2 import (
    AnalysisPlanV2,
    AnalysisResultV2,
    PlanParameters,
    PlanQuestion,
    ResultInterpretation,
)

LEASE_SECONDS = 120


def now():
    return datetime.now(UTC)


def reference(kind, value):
    return SourceRef(kind=kind, id=value.id, revision=value.revision, hash=canonical_hash(value))


def token(plan, snapshot):
    body = plan.model_dump(
        mode="json",
        exclude={
            "proposal_token",
            "status",
            "approval",
            "validity",
            "invalidated_at",
            "stale_reasons",
            "execution_status",
            "data_authorized",
        },
    )
    encoded = json.dumps(
        {"proposal": body, "snapshot": snapshot.model_dump(mode="json") if snapshot else None},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )
    return hashlib.sha256(encoded.encode()).hexdigest()


class AnalysisServiceV2:
    def __init__(self, diagnostics, contexts):
        self.diagnostics = diagnostics
        self.intents = diagnostics.intents
        self.workspace = diagnostics.workspace
        self.store = diagnostics.store
        self.contexts = contexts

    def _get(self, project, kind, id_, db=None):
        self.workspace.sources.require(project)
        value = self.store.get(project, kind, id_, db)
        if not value:
            missing()
        return value

    def _put_state(self, db, project, kind, id_, value):
        previous = self.store.get(project, kind, id_, db)
        revision = previous["revision"] if previous else 0
        self.store.put(db, project, kind, id_, {**value, "revision": revision + 1}, revision)

    def resolve(self, project, intent_id, diagnostic_ids):
        intent, dataset, dictionary, rows, refs = self.diagnostics.resolve(project, intent_id)
        context = (
            self.contexts.get(project) if intent.objective_id or intent.hypothesis_id else None
        )
        if context:
            if intent.objective_id and intent.objective_id not in {
                o.id for o in context.specific_objectives
            }:
                fail(
                    "El objetivo vinculado ya no existe; revisa la intención.",
                    "source_stale",
                    409,
                )
            if intent.hypothesis_id and intent.hypothesis_id not in {
                h.id for h in context.hypotheses
            }:
                fail(
                    "La hipótesis vinculada ya no existe; revisa la intención.",
                    "source_stale",
                    409,
                )
            refs.append(
                SourceRef(
                    kind="context",
                    id=project,
                    revision=context.revision,
                    hash=canonical_hash(context),
                )
            )
        diagnostics = []
        for id_ in dict.fromkeys(diagnostic_ids):
            diagnostic = self.diagnostics.get(project, id_)
            if diagnostic.intent_id != intent_id:
                fail(
                    "El diagnóstico pertenece a otra intención.",
                    "incompatible_variables",
                    422,
                )
            if diagnostic.state != "current":
                fail("Actualiza los diagnósticos de esta intención.", "source_stale", 409)
            diagnostics.append(diagnostic)
            refs.append(reference("diagnostic", diagnostic))
        return PlanningInputV2(intent, dataset, dictionary, rows, diagnostics, context), refs

    def propose(self, project, request):
        intent = self.intents.get(project, request.intent_id)
        if intent.revision != request.intent_revision or (
            request.dataset_id is not None and request.dataset_id != intent.dataset_id
        ):
            fail("La intención cambió. Recarga antes de proponer.", "source_stale", 409)
        snapshot, decision, data = None, None, None
        refs = [reference("intent", intent)]
        questions = []
        try:
            data, refs = self.resolve(project, intent.id, request.diagnostic_ids)
            if (
                request.dataset_revision is not None
                and request.dataset_revision != data.dataset.revision
            ):
                fail("La tabla cambió.", "source_stale", 409)
            decision = select(data)
            questions = decision.questions
            if intent.confirmation:
                by_kind = {r.kind: r for r in refs}
                variables = [
                    SnapshotVariableV2(
                        id=v.id,
                        column_ids=v.column_ids,
                        name=v.name,
                        measurement_scale=v.measurement_scale,
                    )
                    for v in data.dictionary.variables
                    if v.id in intent.variable_ids
                ]
                snapshot = AnalysisSnapshotV2(
                    id=str(uuid4()),
                    project_id=project,
                    created_at=now(),
                    source_refs=refs,
                    context_ref=by_kind.get("context"),
                    dictionary_ref=by_kind["dictionary"],
                    dataset_ref=by_kind["dataset"],
                    intent_ref=by_kind["intent"],
                    profile_ref=by_kind["profile"],
                    diagnostic_refs=[r for r in refs if r.kind == "diagnostic"],
                    variables=variables,
                    intent=intent,
                    source_fingerprint=snapshot_fingerprint(refs, VERSIONS),
                    dependency_fields=[
                        "/intent",
                        "/dataset",
                        "/dictionary",
                        "/profile",
                        "/diagnostics",
                    ]
                    + (["/context"] if data.context else []),
                    policy_versions=VERSIONS,
                    confirmed_facts={
                        name: getattr(intent, name)
                        for name in (
                            "question",
                            "observational_unit",
                            "identification",
                            "comparison_notes",
                        )
                        if getattr(intent, name).confirmation
                    },
                )
        except ContextError as exc:
            if exc.status not in {404, 409, 422}:
                raise
            # An unresolved input is a durable scientific clarification, never a fabricated source.
            refs = [reference("intent", intent)]
            questions = [
                PlanQuestion(
                    code="evidence",
                    field="evidence",
                    question=exc.message,
                    destination="datasets"
                    if "perfil" in exc.message
                    or "tabla" in exc.message
                    or "diccionario" in exc.message
                    else "analysis",
                )
            ]
        technique = decision.technique if decision and not questions else None
        plan = AnalysisPlanV2(
            id=str(uuid4()),
            project_id=project,
            snapshot_ref=reference("snapshot", snapshot) if snapshot else None,
            intent_id=intent.id,
            dataset_id=intent.dataset_id,
            status="proposed" if technique else "needs_clarification",
            technique=technique,
            parameters=PlanParameters(
                alpha=intent.alpha,
                alternative=intent.alternative,
                calculation_method=METHODS[technique] if technique else "pending",
            ),
            rationale=decision.rationale
            if decision
            else "Completa la evidencia indicada y solicita otra propuesta.",
            evidence_refs=refs,
            pending_questions=questions,
            limitations=decision.limitations if decision else [],
            source_fingerprint=snapshot_fingerprint(refs, VERSIONS),
            proposal_token="0" * 64,
            created_at=now(),
            question=intent.question.value or "Resumen descriptivo",
            variable_names=[
                v.name.value or v.id
                for v in data.dictionary.variables
                if v.id in intent.variable_ids
            ]
            if data
            else [],
            case_counts=decision.counts if decision else None,
            policy_versions=VERSIONS,
            data_authorization_required=not data or data.dataset.synthetic is not True,
        )
        plan.proposal_token = token(plan, snapshot)
        with self.store.transaction() as db:
            # Same source resolution again under the shared SQLite write lock.
            if any(r.kind == "dataset" for r in refs):
                _, latest = self.resolve(project, intent.id, request.diagnostic_ids)
                if latest != refs:
                    fail("Las dependencias cambiaron al proponer.", "source_stale", 409)
            elif reference("intent", self.intents.get(project, intent.id)) != refs[0]:
                fail("La intención cambió al proponer.", "source_stale", 409)
            if snapshot:
                self.store.put(
                    db, project, "snapshot", snapshot.id, snapshot.model_dump(mode="json"), 0
                )
            self.store.put(db, project, "plan", plan.id, plan.model_dump(mode="json"), 0)
        return plan

    def _snapshot(self, plan):
        if not plan.snapshot_ref:
            return None
        snapshot = AnalysisSnapshotV2.model_validate(
            self._get(plan.project_id, "snapshot", plan.snapshot_ref.id)
        )
        if reference("snapshot", snapshot) != plan.snapshot_ref:
            fail(
                "La evidencia almacenada no coincide con la propuesta.", "storage_unavailable", 503
            )
        return snapshot

    def _reasons(self, plan):
        invalid = self.store.get(plan.project_id, "invalidation", plan.id)
        if invalid:
            return invalid["reasons"]
        if plan.policy_versions != VERSIONS:
            return ["Cambió la política de selección o la versión del motor."]
        try:
            if any(r.kind == "dataset" for r in plan.evidence_refs):
                _, refs = self.resolve(
                    plan.project_id,
                    plan.intent_id,
                    [r.id for r in plan.evidence_refs if r.kind == "diagnostic"],
                )
            else:
                refs = [reference("intent", self.intents.get(plan.project_id, plan.intent_id))]
            if snapshot_fingerprint(refs, VERSIONS) != plan.source_fingerprint:
                return [
                    "Cambió la intención, sus fuentes, diccionario, perfil o evidencia vinculada."
                ]
        except ContextError as exc:
            if exc.status not in {404, 409, 422}:
                raise
            return [exc.message]
        return []

    def _recover(self, db, project, plan_id):
        state = self.store.get(project, "execution", plan_id, db)
        if (
            state
            and state["status"] == "running"
            and datetime.fromisoformat(state["lease_until"]) <= now()
        ):
            state = {
                **state,
                "status": "failed",
                "error": "interrupted: venció la reserva del cálculo; no se acredita finalización",
                "finished_at": now().isoformat(),
            }
            self._put_state(db, project, "attempt", state["attempt_id"], state)
            self._put_state(db, project, "execution", plan_id, state)
        return state

    def get(self, project, plan_id):
        plan = AnalysisPlanV2.model_validate(self._get(project, "plan", plan_id))
        reasons = self._reasons(plan)
        with self.store.transaction() as db:
            if reasons and not self.store.get(project, "invalidation", plan_id, db):
                self._put_state(
                    db,
                    project,
                    "invalidation",
                    plan_id,
                    {"reasons": reasons, "at": now().isoformat()},
                )
            state = self._recover(db, project, plan_id)
        approval = self.store.get(project, "approval", plan_id)
        if approval:
            plan.status, plan.approval = (
                "approved",
                Confirmation.model_validate(approval["confirmation"]),
            )
        if reasons:
            plan.validity, plan.stale_reasons = "stale", reasons
            plan.invalidated_at = datetime.fromisoformat(
                self.store.get(project, "invalidation", plan_id)["at"]
            )
        plan.data_authorized = bool(self.store.get(project, "data_authorization", plan_id))
        plan.execution_status = state["status"] if state else "not_started"
        return plan

    def list(self, project):
        self.workspace.sources.require(project)
        return [self.get(project, p["id"]) for p in self.store.all(project, "plan")]

    def _guard(self, plan, supplied_token):
        snapshot = self._snapshot(plan)
        if supplied_token != plan.proposal_token or token(plan, snapshot) != plan.proposal_token:
            fail("La aprobación no corresponde a la propuesta exacta.", "approval_mismatch", 409)
        reasons = self._reasons(plan)
        if reasons:
            fail(" ".join(reasons), "source_stale", 409)
        if plan.pending_questions or not plan.technique:
            fail("Resuelve las aclaraciones y solicita una nueva propuesta.", "not_approved", 409)
        return snapshot

    def authorize(self, project, plan_id, request):
        if not request.confirm:
            fail(
                "Confirma que tienes autorización para calcular con estas fuentes.",
                "consent_required",
                403,
            )
        with self.store.transaction() as db:
            plan = AnalysisPlanV2.model_validate(self._get(project, "plan", plan_id, db))
            self._guard(plan, request.proposal_token)
            if not self.store.get(project, "data_authorization", plan_id, db):
                self._put_state(
                    db,
                    project,
                    "data_authorization",
                    plan_id,
                    {
                        "source_fingerprint": plan.source_fingerprint,
                        "actor_ref": self.workspace.sources.actor_ref,
                        "at": now().isoformat(),
                    },
                )
        return self.get(project, plan_id)

    def _authorized(self, plan, db):
        if plan.data_authorization_required and not self.store.get(
            plan.project_id, "data_authorization", plan.id, db
        ):
            fail(
                "Autoriza explícitamente el cálculo local con estas fuentes; esto no autoriza "
                "enviarlas a IA.",
                "consent_required",
                403,
            )

    def approve(self, project, plan_id, request):
        if not request.confirm:
            fail("La aprobación requiere confirmación explícita.", "not_approved", 409)
        self.get(project, plan_id)
        with self.store.transaction() as db:
            plan = AnalysisPlanV2.model_validate(self._get(project, "plan", plan_id, db))
            self._guard(plan, request.proposal_token)
            self._authorized(plan, db)
            if not self.store.get(project, "approval", plan_id, db):
                confirmation = Confirmation(
                    actor_ref=self.workspace.sources.actor_ref, confirmed_at=now(), revision=1
                )
                self._put_state(
                    db,
                    project,
                    "approval",
                    plan_id,
                    {
                        "confirmation": confirmation.model_dump(mode="json"),
                        "proposal_token": request.proposal_token,
                    },
                )
        return self.get(project, plan_id)

    def execute(self, project, plan_id, request):
        self.get(project, plan_id)
        attempt_id = f"{plan_id}:{request.request_id}"
        with self.store.transaction() as db:
            plan = AnalysisPlanV2.model_validate(self._get(project, "plan", plan_id, db))
            if request.proposal_token != plan.proposal_token:
                fail("El token no corresponde a esta propuesta.", "approval_mismatch", 409)
            state = self._recover(db, project, plan_id)
            previous = self.store.get(project, "attempt", attempt_id, db)
            # Returning persisted output is not execution, even after its sources became stale.
            if previous and previous.get("result_id"):
                result_id = previous["result_id"]
            elif state and state["status"] == "completed":
                result_id = state["result_id"]
            else:
                result_id = None
                if previous:
                    fail(
                        "Este intento está en curso o falló; consulta su estado. Un fallo "
                        "requiere una nueva clave.",
                        "execution_conflict",
                        409,
                    )
                if state and state["status"] == "running":
                    fail(
                        "Ya existe una ejecución en curso para esta propuesta.",
                        "execution_conflict",
                        409,
                    )
                snapshot = self._guard(plan, request.proposal_token)
                if not self.store.get(project, "approval", plan_id, db):
                    fail("Aprueba esta propuesta antes de ejecutarla.", "not_approved", 409)
                self._authorized(plan, db)
                data, _ = self.resolve(
                    project,
                    plan.intent_id,
                    [r.id for r in plan.evidence_refs if r.kind == "diagnostic"],
                )
                state = {
                    "status": "running",
                    "attempt_id": attempt_id,
                    "request_id": str(request.request_id),
                    "started_at": now().isoformat(),
                    "lease_until": (now() + timedelta(seconds=LEASE_SECONDS)).isoformat(),
                    "result_id": None,
                }
                self._put_state(db, project, "attempt", attempt_id, state)
                self._put_state(db, project, "execution", plan_id, state)
        if result_id:
            return self.result(project, result_id)
        failure = None
        try:
            counts, metrics, tables, warnings = execute(
                ExecutionInputV2(snapshot, data.dataset, data.dictionary, data.rows, plan.technique)
            )
            if counts != plan.case_counts or any(
                case_counts(d.profile, plan.technique) != counts for d in data.diagnostics
            ):
                raise StatisticalCalculationError(
                    "Los conteos del cálculo no coinciden con la evidencia aprobada."
                )
        except (ValueError, ArithmeticError) as exc:
            failure = str(exc)
            counts, metrics, tables, warnings = plan.case_counts, [], [], [failure]
        except Exception:
            # Persist failure without exposing internal exception details.
            failure = (
                "Fallo inesperado del motor; el intento se conserva y permite reintento explícito."
            )
            counts, metrics, tables, warnings = plan.case_counts, [], [], [failure]
        result = AnalysisResultV2(
            id=str(uuid4()),
            project_id=project,
            analysis_plan_id=plan.id,
            snapshot_ref=plan.snapshot_ref,
            dataset_id=plan.dataset_id,
            status="failed" if failure else "completed",
            created_at=now(),
            engine_version=VERSIONS["engine"],
            method_version=plan.parameters.calculation_method + ":" + VERSIONS["methods"],
            source_fingerprint=plan.source_fingerprint,
            source_refs=plan.evidence_refs,
            case_counts=counts,
            metrics=metrics,
            tables=tables,
            assumptions=[c for d in data.diagnostics for c in d.checks],
            warnings=warnings,
            limitations=plan.limitations,
            question=plan.question,
            technique=plan.technique,
            variable_names=plan.variable_names,
            interpretation=None
            if failure
            else ResultInterpretation(
                text=(
                    f"Se analizaron {counts.used} de {counts.total} casos "
                    f"mediante {plan.technique}. "
                    "Consulta las métricas y sus límites; este resultado no establece causalidad."
                ),
                metric_keys=[m.key for m in metrics],
            ),
        )
        with self.store.transaction() as db:
            state = self._recover(db, project, plan_id)
            try:
                dependency_reasons = self._reasons(plan)
            except ContextError:
                dependency_reasons = [
                    "No se pudo revalidar la fuente al publicar; salida histórica sin "
                    "vigencia acreditada."
                ]
            owns = state and state["attempt_id"] == attempt_id and state["status"] == "running"
            reservation_error = (
                None if owns else "El intento perdió su reserva; no acredita ejecución vigente."
            )
            # A lost lease belongs to this attempt, not to the plan's dependencies.
            result_reasons = [*dependency_reasons]
            if reservation_error:
                result_reasons.append(reservation_error)
            if result_reasons:
                result.validity, result.stale_reasons = "stale", result_reasons
            if dependency_reasons and not self.store.get(project, "invalidation", plan_id, db):
                self._put_state(
                    db,
                    project,
                    "invalidation",
                    plan_id,
                    {"reasons": dependency_reasons, "at": now().isoformat()},
                )
            self.store.put(db, project, "result", result.id, result.model_dump(mode="json"), 0)
            finished = {
                "status": "completed" if not failure and owns else "failed",
                "attempt_id": attempt_id,
                "request_id": str(request.request_id),
                "result_id": result.id,
                "error": failure or reservation_error,
                "finished_at": now().isoformat(),
            }
            self._put_state(db, project, "attempt", attempt_id, finished)
            if owns:
                self._put_state(db, project, "execution", plan_id, finished)
        return self.result(project, result.id)

    def result(self, project, id_):
        result = AnalysisResultV2.model_validate(self._get(project, "result", id_))
        plan = self.get(project, result.analysis_plan_id)
        if plan.validity == "stale":
            result.validity = "stale"
            result.stale_reasons = list(dict.fromkeys([*result.stale_reasons, *plan.stale_reasons]))
        return result

    def results(self, project):
        self.workspace.sources.require(project)
        return [self.result(project, r["id"]) for r in self.store.all(project, "result")]

    def attempts(self, project, plan_id):
        self.get(project, plan_id)
        return [
            a
            for a in self.store.all(project, "attempt")
            if a["attempt_id"].startswith(plan_id + ":")
        ]
