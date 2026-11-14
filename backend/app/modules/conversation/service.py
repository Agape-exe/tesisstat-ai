import sqlite3
from time import monotonic
from uuid import UUID

from pydantic import Field

from app.modules.conversation.models import ConversationError, MessageDraft
from app.modules.conversation.ports import ConversationRepository, ResponseGenerator
from app.modules.conversation.research_context import ResearchContextBuilder
from app.modules.research.projects.use_cases import ProjectService
from app.orchestration.multiagent.graph import MultiagentWorkflow
from app.orchestration.multiagent.state import ExecutionBudget
from app.orchestration.multiagent.tools import VerifiedPlanningReader
from app.shared.adapters.cloudflare import CloudflareLanguageModel, CloudflareSettings
from app.shared.adapters.gemini import GeminiLanguageModel
from app.shared.ai_errors import AIError

ERRORS = {
    "not_configured": "Cloudflare no está configurado. Puedes consultar tu historial.",
    "timeout": "La IA tardó demasiado. No se generó una respuesta confirmada.",
    "quota": "Cloudflare alcanzó su límite de cuota. Intenta más tarde.",
    "credentials": "Cloudflare rechazó las credenciales. Revisa la configuración del backend.",
    "invalid_response": "La IA devolvió una respuesta inválida o incompleta.",
    "input_limit": "El mensaje y el contexto superan el límite del proveedor. Acorta tu pregunta.",
    "output_limit": "El límite de respuesta no es compatible con la configuración del proveedor.",
    "provider_error": "No se pudo obtener una respuesta de Cloudflare. Intenta más tarde.",
    "graph_step_limit": "Se alcanzó el límite de pasos del flujo. Acota la consulta.",
    "model_call_limit": "Se alcanzó el presupuesto de llamadas al modelo.",
    "planning_limit": "Se alcanzó el presupuesto de planificación de esta consulta.",
    "source_mismatch": "Las fuentes no corresponden al proyecto activo. Actualiza el contexto.",
}


class ConversationSettings(CloudflareSettings):
    conversation_max_message_characters: int = Field(default=2000, ge=1, le=16000)
    conversation_page_size: int = Field(default=50, ge=2, le=200)
    conversation_history_turns: int = Field(default=8, ge=0, le=50)
    conversation_max_request_bytes: int = Field(default=32768, ge=1024, le=131072)
    conversation_max_context_bytes: int = Field(default=20000, ge=2000, le=40000)
    conversation_max_output_tokens: int = Field(default=1024, ge=256, le=4096)
    multiagent_max_steps: int = Field(default=4, ge=1, le=16)
    multiagent_max_model_calls: int = Field(default=1, ge=0, le=1)
    multiagent_max_planning_operations: int = Field(default=1, ge=0, le=1)
    multiagent_timeout_seconds: float = Field(default=120, gt=0, le=120)


class ConversationService:
    def __init__(
        self,
        projects: ProjectService,
        repository: ConversationRepository,
        provider: ResponseGenerator,
        settings: ConversationSettings,
        research_context: ResearchContextBuilder | None = None,
    ):
        self.projects, self.repository, self.provider, self.settings = (
            projects,
            repository,
            provider,
            settings,
        )
        self.research_context = research_context
        self.workflow = MultiagentWorkflow(
            provider,
            research_context,
            VerifiedPlanningReader(research_context) if research_context else None,
            provider_kind="gemini"
            if isinstance(provider, GeminiLanguageModel)
            else "cloudflare_workers_ai"
            if isinstance(provider, CloudflareLanguageModel)
            else "injected",
            model=getattr(provider, "model", None),
        )

    def status(self, project_id: UUID):
        project = self.projects.get(project_id)
        return {
            "provider_configured": self.provider.configured,
            "model": self.settings.cloudflare_model,
            "max_message_characters": self.settings.conversation_max_message_characters,
            "timeout_seconds": self.settings.cloudflare_timeout_seconds,
            "external_provider": "Cloudflare Workers AI",
            "context": "Fuentes persistidas del proyecto, seleccionadas según tu pregunta.",
            "consent_scope": "research_context_v2",
            "project_title": project.title,
            "research_context": self.research_context.build(project_id).summary()
            if self.research_context
            else None,
        }

    def create(self, project_id: UUID, title: str):
        self.projects.get(project_id)
        return self.repository.create(project_id, title)

    def list(self, project_id: UUID, offset: int):
        self.projects.get(project_id)
        return self.repository.list(project_id, self.settings.conversation_page_size, offset)

    def get(self, project_id: UUID, conversation_id: UUID, before: int | None = None):
        self.projects.get(project_id)
        conversation = self.repository.get(project_id, conversation_id)
        messages = self.repository.messages(
            conversation_id, self.settings.conversation_page_size, before
        )
        return {
            "conversation": conversation,
            "messages": messages,
            "has_more": bool(messages and messages[0].sequence > 1),
        }

    def delete(self, project_id: UUID, conversation_id: UUID):
        self.get(project_id, conversation_id)
        self.repository.delete(project_id, conversation_id)

    def send(self, project_id: UUID, conversation_id: UUID, draft: MessageDraft):
        project = self.projects.get(project_id)
        self.repository.get(project_id, conversation_id)
        if len(draft.content) > self.settings.conversation_max_message_characters:
            raise ConversationError(
                "message_limit", "El mensaje supera la longitud permitida.", 422
            )
        # Persisted idempotency is checked before provider access, including after a restart.
        cached = self.repository.claim(
            conversation_id,
            draft.request_id,
            draft.content,
            max(self.settings.cloudflare_timeout_seconds, self.settings.multiagent_timeout_seconds),
        )
        if cached is not None:
            return {"messages": cached}
        trace = {"consent_scope": draft.consent_scope}
        self.workflow.initialize_trace(trace)
        deadline = monotonic() + self.settings.multiagent_timeout_seconds
        try:
            if not self.provider.configured:
                raise AIError("not_configured")
            history = self.repository.messages(
                conversation_id, self.settings.conversation_history_turns * 2, completed_only=True
            )
            output_tokens = min(
                self.settings.conversation_max_output_tokens,
                self.settings.cloudflare_max_output_tokens,
            )
            budget = min(
                self.settings.conversation_max_context_bytes,
                self.settings.cloudflare_max_input_tokens - output_tokens - 512,
            )
            state = self.workflow.invoke(
                {
                    "project_id": project_id,
                    "conversation_id": conversation_id,
                    "title": project.title,
                    "project_version": project.updated_at.isoformat(),
                    "content": draft.content,
                    "history": history,
                    "request_type": "general",
                    "research": None,
                    "planning": {},
                    "warnings": [],
                    "answer": "",
                    "context_bytes": budget,
                    "output_tokens": output_tokens,
                    "trace": trace,
                    "budget": ExecutionBudget(
                        deadline=deadline,
                        max_steps=self.settings.multiagent_max_steps,
                        max_calls=self.settings.multiagent_max_model_calls,
                        max_planning=self.settings.multiagent_max_planning_operations,
                    ),
                }
            )
            return {
                "messages": self.repository.complete(
                    conversation_id, draft.request_id, state["answer"], trace
                )
            }
        except (AIError, TimeoutError) as exc:
            code = exc.code if isinstance(exc, AIError) else "timeout"
            trace.setdefault("multiagent", {}).setdefault("errors", [])
            if code not in trace["multiagent"]["errors"]:
                trace["multiagent"]["errors"].append(code)
            self.repository.fail(conversation_id, draft.request_id, trace)
            raise ConversationError(
                code, ERRORS.get(code, ERRORS["provider_error"]), 504 if code == "timeout" else 503
            ) from None
        except sqlite3.Error:
            self.repository.fail(conversation_id, draft.request_id)
            raise
        except Exception:
            # Do not log prompts, provider payloads, secrets, or raw exception messages.
            trace["multiagent"]["errors"].append("provider_error")
            self.repository.fail(conversation_id, draft.request_id, trace)
            raise ConversationError("provider_error", ERRORS["provider_error"], 503) from None
