import json
import sqlite3
from uuid import UUID

from pydantic import Field

from app.modules.conversation.context import build_context
from app.modules.conversation.models import ConversationError, MessageDraft
from app.modules.conversation.ports import ConversationRepository, ResponseGenerator
from app.modules.research.projects.use_cases import ProjectService
from app.shared.adapters.cloudflare import CloudflareSettings
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
}


class ConversationSettings(CloudflareSettings):
    conversation_max_message_characters: int = Field(default=2000, ge=1, le=16000)
    conversation_page_size: int = Field(default=50, ge=2, le=200)
    conversation_history_turns: int = Field(default=8, ge=0, le=50)
    conversation_max_request_bytes: int = Field(default=32768, ge=1024, le=131072)
    conversation_max_context_bytes: int = Field(default=10000, ge=2000, le=20000)
    conversation_max_output_tokens: int = Field(default=1024, ge=256, le=4096)


class ConversationService:
    def __init__(
        self,
        projects: ProjectService,
        repository: ConversationRepository,
        provider: ResponseGenerator,
        settings: ConversationSettings,
    ):
        self.projects, self.repository, self.provider, self.settings = (
            projects,
            repository,
            provider,
            settings,
        )

    def status(self, project_id: UUID):
        self.projects.get(project_id)
        return {
            "provider_configured": self.provider.configured,
            "model": self.settings.cloudflare_model,
            "max_message_characters": self.settings.conversation_max_message_characters,
            "timeout_seconds": self.settings.cloudflare_timeout_seconds,
            "external_provider": "Cloudflare Workers AI",
            "context": "Solo título e historial reciente; sin documentos ni resultados.",
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
            self.settings.cloudflare_timeout_seconds,
        )
        if cached is not None:
            return {"messages": cached}
        try:
            if not self.provider.configured:
                raise AIError("not_configured")
            history = self.repository.messages(
                conversation_id, self.settings.conversation_history_turns * 2, completed_only=True
            )
            budget = min(
                self.settings.conversation_max_context_bytes,
                self.settings.cloudflare_max_input_tokens - 512,
            )
            context = build_context(project.title, history, draft.content, budget)
            if len(json.dumps(context, ensure_ascii=False).encode()) > budget:
                raise AIError("input_limit")
            answer = self.provider.chat(
                context,
                max_tokens=min(
                    self.settings.conversation_max_output_tokens,
                    self.settings.cloudflare_max_output_tokens,
                ),
            )
            if not isinstance(answer, str) or not answer.strip() or len(answer.encode()) > 65536:
                raise AIError("invalid_response")
            return {
                "messages": self.repository.complete(
                    conversation_id, draft.request_id, answer.strip()
                )
            }
        except (AIError, TimeoutError) as exc:
            self.repository.fail(conversation_id, draft.request_id)
            code = exc.code if isinstance(exc, AIError) else "timeout"
            raise ConversationError(
                code, ERRORS.get(code, ERRORS["provider_error"]), 504 if code == "timeout" else 503
            ) from None
        except sqlite3.Error:
            self.repository.fail(conversation_id, draft.request_id)
            raise
        except Exception:
            # Do not log prompts, provider payloads, secrets, or raw exception messages.
            self.repository.fail(conversation_id, draft.request_id)
            raise ConversationError("provider_error", ERRORS["provider_error"], 503) from None
