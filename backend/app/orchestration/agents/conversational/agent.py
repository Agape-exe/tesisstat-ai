from time import monotonic

from app.modules.conversation.context import build_context
from app.modules.conversation.ports import ResponseGenerator
from app.orchestration.multiagent.state import AgentState
from app.shared.ai_errors import AIError


class ConversationalAgent:
    def __init__(self, provider: ResponseGenerator):
        self.provider = provider

    def run(self, state: AgentState) -> dict:
        budget = state["budget"]
        guidance = {
            "request_type": state["request_type"],
            "planning": state["planning"],
            "warnings": state["warnings"][:12],
        }
        if state["request_type"] == "blocked_execution":
            guidance["action"] = (
                "Solicitud bloqueada: no se ejecutó ni modificó nada. Explica que debe usar "
                "planificación, revisión, aprobación humana y ejecución fuera del chat."
            )
        elif state["request_type"] == "clarification":
            guidance["action"] = (
                "Pide precisar si consulta metodología, datos, resultados o planificación."
            )
        context = build_context(
            state["title"],
            state["history"],
            state["content"],
            state["context_bytes"],
            state["research"],
            state["trace"],
            guidance,
            {"id": str(state["project_id"]), "version": state.get("project_version", "current")},
        )
        if budget.calls >= budget.max_calls:
            raise AIError("model_call_limit")
        if monotonic() >= budget.deadline:
            raise AIError("timeout")
        budget.calls += 1
        state["trace"]["multiagent"]["provider_calls"] = budget.calls
        answer = self.provider.chat(context, max_tokens=state["output_tokens"])
        if not isinstance(answer, str) or not answer.strip() or len(answer.encode()) > 65536:
            raise AIError("invalid_response")
        return {"answer": answer.strip()}
