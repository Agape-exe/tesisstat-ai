"""C7 tutor over existing conversations, provider, suggestions and analysis services.

No model tools, approval operations or statistical engines are exposed here.
"""

import json
from datetime import UTC, datetime
from time import monotonic
from uuid import UUID, uuid4

from pydantic import ValidationError

from app.modules.conversation.models import ConversationError
from app.modules.conversation.service import ERRORS
from app.modules.conversation.tutor_context import HELP, TutorContextBuilder, digest
from app.modules.conversation.tutor_privacy import (
    SYSTEM,
    orientation,
    outbound_context,
    topics,
    validate_prose,
)
from app.modules.research.context.import_models import SuggestionCreate
from app.modules.research.context.repository import ContextError
from app.modules.research.context.suggestions import SuggestionService
from app.orchestration.analysis_v2_service import reference
from app.shared.adapters.cloudflare import CloudflareLanguageModel
from app.shared.ai_errors import AIError
from app.shared.tutor_v2 import ResultExplanationV2, TutorAnswerV2, TutorSelectionV2


class TutorService:
    def __init__(self, conversations, analysis, contexts):
        self.conversations, self.analysis, self.contexts = conversations, analysis, contexts
        self.repository = conversations.repository
        self.store, self.settings = analysis.store, conversations.settings
        self.builder = TutorContextBuilder(analysis, contexts)
        self.suggestions = SuggestionService(contexts)

    def consent(self, project):
        self.analysis.workspace.sources.require(project)
        return self.store.get(project, "tutor_consent", project) or {
            "revision": 0,
            "granted": False,
            "consent_scope": "tutor_context_v3",
        }

    def set_consent(self, project, body):
        self.analysis.workspace.sources.require(project)
        with self.store.transaction() as db:
            value = {
                "revision": body.expected_revision + 1,
                "granted": body.granted,
                "consent_scope": body.consent_scope,
                "at": datetime.now(UTC).isoformat(),
                "actor_ref": self.analysis.workspace.sources.actor_ref,
            }
            self.store.put(db, project, "tutor_consent", project, value, body.expected_revision)
        return value

    def _consent(self, project, revision):
        value = self.consent(project)
        if not value["granted"] or value["revision"] != revision:
            raise ConversationError(
                "consent_required",
                "Autoriza el alcance tutor_context_v3 vigente. "
                "El consentimiento anterior o revocado no permite enviar a IA.",
                403,
            )

    def status(self, project, selection):
        context, selected_result = self.builder.build(project, selection)
        selected_plan_id = selection.plan_id or (
            selected_result.analysis_plan_id if selected_result else None
        )
        return {
            "provider_configured": self.conversations.provider.configured,
            "provider_kind": "cloudflare_workers_ai"
            if isinstance(self.conversations.provider, CloudflareLanguageModel)
            else "controlled_test",
            "consent": self.consent(project),
            "context": context,
            "static_help": HELP[selection.stage],
            "max_message_characters": self.settings.conversation_max_message_characters,
            "privacy": "Se envían etapa, temas estadísticos detectados, escalas, estados y "
            "métricas agregadas pertinentes bajo alias. El texto libre de mensajes, historial, "
            "contexto, nombres y categorías permanece local. No se envían filas ni documentos.",
            "choices": {
                "datasets": [
                    {"id": d.id, "label": d.name} for d in self.analysis.workspace.datasets(project)
                ],
                "intents": [
                    {"id": i.id, "label": i.question.value or f"Análisis {n + 1}"}
                    for n, i in enumerate(self.analysis.intents.list(project))
                ],
                "plans": [
                    {
                        "id": p["id"],
                        "intent_id": p["intent_id"],
                        "label": p["question"],
                        "validity": context.intent_summary.get("plan_validity", "unverified")
                        if p["id"] == selected_plan_id
                        else "unverified",
                    }
                    for p in self.store.all(project, "plan")
                ],
                "results": [
                    {
                        "id": r["id"],
                        "plan_id": r["analysis_plan_id"],
                        "dataset_id": r["dataset_id"],
                        "label": r["question"],
                        "validity": context.intent_summary.get("result_validity", "unverified")
                        if selected_result and r["id"] == selected_result.id
                        else "unverified",
                        "status": r["status"],
                    }
                    for r in self.store.all(project, "result")
                ],
            },
        }

    def send(self, project, conversation_id, draft):
        self.analysis.workspace.sources.require(project)
        self.repository.get(UUID(project), conversation_id)
        if len(draft.content) > self.settings.conversation_max_message_characters:
            raise ConversationError(
                "message_limit", "Acorta el mensaje a la longitud permitida.", 422
            )
        selection = TutorSelectionV2.model_validate(
            draft.model_dump(include=set(TutorSelectionV2.model_fields))
        )
        context, result = self.builder.build(project, selection)
        base_context_revision = next(
            (r.revision for r in context.source_refs if r.kind == "context" and r.id == project), 0
        )
        trace = {
            "tutor_version": "contextual-2.0.0",
            "provider_kind": "cloudflare_workers_ai"
            if isinstance(self.conversations.provider, CloudflareLanguageModel)
            else "controlled_test",
            "consent_revision": draft.consent_revision,
            "consent_scope": "tutor_context_v3",
            "snapshot": context.context_fingerprint,
            "stage": context.stage,
            "sources": [r.model_dump(mode="json") for r in context.source_refs],
            "historical_refs": [r.model_dump(mode="json") for r in context.historical_refs],
            "result_ref": reference("result", result).model_dump(mode="json") if result else None,
            "provider_calls": 0,
            "privacy_policy": "closed-topics-v1",
            "metric_refs": [],
            "actions": [],
        }
        # Bind request_id to the user's selection as well as text, but not to changing sources.
        # An exact retry returns its original references, including after sources change.
        cached = self.repository.claim(
            conversation_id,
            draft.request_id,
            draft.content,
            self.settings.cloudflare_timeout_seconds,
            fingerprint=digest(draft.model_dump(mode="json")),
            context=trace,
        )
        if cached is not None:
            return {"messages": cached}
        started = monotonic()
        try:
            self._consent(project, draft.consent_revision)
            if not self.conversations.provider.configured:
                raise AIError("not_configured")
            query_topics = topics(draft.content)
            payload, metric_map = outbound_context(context, result, query_topics)
            payload["query_topics"] = query_topics
            trace["metrics_omitted"] = payload["metrics_omitted"]
            # Old source conversations do not contribute claims about a new analysis.
            history = self.repository.messages(
                conversation_id, self.settings.conversation_history_turns * 2, completed_only=True
            )
            payload["history_topics"] = [
                topics(m.content)
                for m in history
                if m.role == "user"
                and m.context
                and m.context.get("snapshot") == context.context_fingerprint
            ][-4:]
            payload["history_omitted"] = bool(history and not payload["history_topics"])
            messages = [
                {"role": "system", "content": SYSTEM},
                {
                    "role": "user",
                    "content": "DATOS_JSON:\n" + json.dumps(payload, ensure_ascii=False),
                },
            ]
            output_tokens = min(
                self.settings.conversation_max_output_tokens,
                self.settings.cloudflare_max_output_tokens,
            )
            limit = min(
                self.settings.conversation_max_context_bytes,
                self.settings.cloudflare_max_input_tokens - output_tokens - 512,
            )
            if len(json.dumps(messages, ensure_ascii=False).encode()) > limit:
                raise AIError("input_limit")
            self._consent(project, draft.consent_revision)
            trace["provider_calls"] = 1
            raw = self.conversations.provider.chat(messages, max_tokens=output_tokens)
            if monotonic() - started > self.settings.cloudflare_timeout_seconds:
                raise AIError("timeout")
            if not isinstance(raw, str) or len(raw.encode()) > 16000:
                raise AIError("invalid_response")
            try:
                answer = TutorAnswerV2.model_validate_json(raw)
            except ValidationError:
                raise AIError("invalid_response") from None
            if (
                not validate_prose(answer.explanation)
                or any(not validate_prose(u.value) for u in answer.updates)
                or any(k not in metric_map for k in answer.metric_keys)
                or any(n >= len(context.allowed_actions) for n in answer.action_indices)
                or len({u.field for u in answer.updates}) != len(answer.updates)
            ):
                raise AIError("invalid_response")
            self._consent(project, draft.consent_revision)
            current, _ = self.builder.build(project, selection)
            trace["context_changed_during_response"] = (
                current.context_fingerprint != context.context_fingerprint
            )
            trace["metric_refs"] = [
                {"result_id": result.id, "key": metric_map[k].key}
                for k in dict.fromkeys(answer.metric_keys)
            ]
            trace["actions"] = [
                context.allowed_actions[n].model_dump(mode="json")
                for n in dict.fromkeys(answer.action_indices)
            ]
            text = answer.explanation
            if not result or result.status != "completed" or not answer.metric_keys:
                # Without metric references no model-written finding is released.
                text = orientation(HELP[context.stage], payload["query_topics"])
                trace["prose_source"] = "template"
            else:
                trace["prose_source"] = "ai_draft"
            if result and result.validity == "stale":
                text = "Resultado histórico desactualizado. " + text
            if trace["context_changed_during_response"]:
                text = (
                    "Las fuentes cambiaron durante la respuesta; "
                    "se conservan sus referencias históricas. " + text
                )
            if answer.updates:
                suggestion = self.suggestions.create(
                    project,
                    SuggestionCreate(
                        expected_revision=base_context_revision,
                        response=json.dumps(
                            {
                                "format_version": "context-import-1.0",
                                **{u.field: u.value for u in answer.updates},
                            },
                            ensure_ascii=False,
                        ),
                    ),
                )
                trace["suggestion_id"] = suggestion.id
                trace["actions"].append(
                    {
                        "kind": "propose_update",
                        "resource_id": suggestion.id,
                        "label": "Revisar sugerencia editable de IA",
                        "destination": "context",
                        "scope": "Revisa el borrador en Contexto antes de aplicar o confirmar.",
                    }
                )
            if result and result.status == "completed" and answer.metric_keys:
                explanation = ResultExplanationV2(
                    id=str(uuid4()),
                    project_id=project,
                    revision=1,
                    result_ref=reference("result", result),
                    context_fingerprint=context.context_fingerprint,
                    text=text,
                    metric_keys=[r["key"] for r in trace["metric_refs"]],
                    created_at=datetime.now(UTC),
                )
                with self.store.transaction() as db:
                    self.store.put(
                        db,
                        project,
                        "result_explanation",
                        explanation.id,
                        explanation.model_dump(mode="json"),
                        0,
                    )
                trace["explanation_id"] = explanation.id
            # Digits in generated prose were rejected. Only the server inserts cited values.
            from app.modules.statistics.presentation_v2 import (
                format_number,
                metric_label,
                metric_unit,
            )

            if answer.metric_keys:
                text += (
                    "\n\nMétricas del resultado "
                    + result.id
                    + ":\n"
                    + "\n".join(
                        f"• {metric_label(metric_map[k])}: "
                        f"{format_number(metric_map[k].value, metric_map[k].key)}"
                        f" {metric_unit(metric_map[k]) or ''}"
                        for k in dict.fromkeys(answer.metric_keys)
                    )
                )

            def delivery_guard(db):
                receipt = self.store.get(project, "tutor_consent", project, db)
                if (
                    not receipt
                    or not receipt["granted"]
                    or receipt["revision"] != draft.consent_revision
                ):
                    raise ConversationError(
                        "consent_required", "El permiso del tutor fue revocado o cambió.", 403
                    )

            return {
                "messages": self.repository.complete(
                    conversation_id, draft.request_id, text, trace, guard=delivery_guard
                )
            }
        except (AIError, TimeoutError) as exc:
            code = exc.code if isinstance(exc, AIError) else "timeout"
            trace["error"] = code
            self.repository.fail(conversation_id, draft.request_id, trace)
            raise ConversationError(
                code,
                ERRORS.get(code, ERRORS["provider_error"]),
                429 if code == "quota" else 504 if code == "timeout" else 503,
            ) from None
        except (ConversationError, ContextError):
            self.repository.fail(conversation_id, draft.request_id, trace)
            raise
        except Exception:
            trace["error"] = "provider_error"
            self.repository.fail(conversation_id, draft.request_id, trace)
            raise ConversationError("provider_error", ERRORS["provider_error"], 503) from None

    def explanations(self, project, result_id):
        self.analysis.result(project, result_id)
        return [
            ResultExplanationV2.model_validate(v)
            for v in self.store.all(project, "result_explanation")
            if v["result_ref"]["id"] == result_id
        ]

    def review(self, project, result_id, explanation_id, body):
        result = self.analysis.result(project, result_id)
        value = next(
            (e for e in self.explanations(project, result_id) if e.id == explanation_id), None
        )
        if value is None:
            raise ContextError("not_found", "No se encontró el borrador en este resultado.", 404)
        if result.validity != "current" or value.result_ref != reference("result", result):
            raise ContextError(
                "source_stale", "El borrador corresponde a un resultado histórico.", 409
            )
        if not validate_prose(body.text):
            raise ContextError(
                "invalid_payload",
                "Usa las referencias de métricas para las cifras; edita solo la explicación.",
            )
        value.text, value.review_status = body.text, "reviewed"
        value.reviewed_at, value.revision = datetime.now(UTC), body.expected_revision + 1
        with self.store.transaction() as db:
            from app.shared.plans_v2 import AnalysisPlanV2

            plan = AnalysisPlanV2.model_validate(
                self.analysis._get(project, "plan", result.analysis_plan_id, db)
            )
            self.analysis._guard(plan, plan.proposal_token)
            self.store.put(
                db,
                project,
                "result_explanation",
                value.id,
                value.model_dump(mode="json"),
                body.expected_revision,
            )
        return value

    def explanation_history(self, project, result_id, explanation_id):
        if not any(e.id == explanation_id for e in self.explanations(project, result_id)):
            raise ContextError("not_found", "No se encontró ese borrador en el resultado.", 404)
        return [
            ResultExplanationV2.model_validate(v)
            for v in self.store.revisions(project, "result_explanation", explanation_id)
        ]
