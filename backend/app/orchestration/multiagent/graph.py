"""Compiled DAG, no checkpointer, dynamic tools, retries, or external tracing."""

from time import monotonic

from langgraph.errors import GraphRecursionError
from langgraph.graph import END, START, StateGraph
from langsmith import tracing_context

from app.modules.conversation.ports import ResponseGenerator
from app.orchestration.agents.conversational.agent import ConversationalAgent
from app.orchestration.agents.research_understanding.agent import ResearchUnderstandingAgent
from app.orchestration.agents.statistical_planner.agent import StatisticalPlanningAgent
from app.orchestration.multiagent.router import classify
from app.orchestration.multiagent.state import AgentState
from app.orchestration.multiagent.tools import PlanningReader, ResearchReader
from app.shared.ai_errors import AIError

FLOW_VERSION = "17a.1"


class MultiagentWorkflow:
    def __init__(
        self,
        provider: ResponseGenerator,
        research: ResearchReader | None,
        planning: PlanningReader | None,
        *,
        provider_kind: str = "injected",
        model: str | None = None,
    ):
        self.provider_kind, self.model = provider_kind, model
        conversational = ConversationalAgent(provider)
        understanding = ResearchUnderstandingAgent(research)
        planner = StatisticalPlanningAgent(planning)
        builder = StateGraph(AgentState)
        builder.add_node("router", self._bounded("router", self._route))
        builder.add_node("research", self._bounded("research", understanding.run))
        builder.add_node("planning", self._bounded("planning", planner.run))
        builder.add_node("conversation", self._bounded("conversation", conversational.run))
        builder.add_edge(START, "router")
        builder.add_conditional_edges(
            "router",
            self._after_router,
            {
                "research": "research",
                "conversation": "conversation",
            },
        )
        builder.add_conditional_edges(
            "research",
            self._after_research,
            {
                "planning": "planning",
                "conversation": "conversation",
            },
        )
        builder.add_edge("planning", "conversation")
        builder.add_edge("conversation", END)
        self.graph = builder.compile()

    @staticmethod
    def _route(state: AgentState) -> dict:
        route = classify(state["content"], state["history"])
        state["trace"]["multiagent"]["request_type"] = route
        return {"request_type": route}

    @staticmethod
    def _after_router(state: AgentState) -> str:
        return (
            "research"
            if state["request_type"]
            in {
                "methodology",
                "data",
                "results",
                "planning",
            }
            else "conversation"
        )

    @staticmethod
    def _after_research(state: AgentState) -> str:
        return "planning" if state["request_type"] == "planning" else "conversation"

    @staticmethod
    def _bounded(name, operation):
        def node(state: AgentState) -> dict:
            budget = state["budget"]
            if monotonic() >= budget.deadline:
                raise AIError("timeout")
            if budget.steps >= budget.max_steps:
                raise AIError("graph_step_limit")
            budget.steps += 1
            trace = state["trace"]["multiagent"]
            trace["nodes"].append(name)
            if name != "router":
                trace["agents"].append(name)
            result = operation(state)
            if name == "planning":
                trace["planning_status"] = result["planning"]["status"]
            if monotonic() >= budget.deadline:
                raise AIError("timeout")
            return result

        return node

    def initialize_trace(self, trace: dict) -> None:
        trace.update(
            snapshot=None,
            sources=[],
            fields=[],
            omitted_facts=0,
            history_changed=False,
            history_turns=0,
        )
        trace["multiagent"] = {
            "flow_version": FLOW_VERSION,
            "engine": "langgraph",
            "request_type": None,
            "nodes": [],
            "agents": [],
            "provider_calls": 0,
            "planning_status": "not_requested",
            "errors": [],
            "provider_kind": self.provider_kind,
            "model": self.model,
            "model_called": False,
            "external_provider_calls": 0,
            "qwen_called": False,
            "planning_operations": 0,
            "steps": 0,
        }

    def invoke(self, state: AgentState) -> AgentState:
        trace = state["trace"]
        self.initialize_trace(trace)
        try:
            # This overrides environment opt-ins as well as automatic SDK tracing.
            with tracing_context(enabled=False):
                result = self.graph.invoke(
                    state,
                    config={
                        "recursion_limit": state["budget"].max_steps + 1,
                        "callbacks": [],
                    },
                )
            return result
        except (AIError, TimeoutError, GraphRecursionError) as exc:
            code = (
                exc.code
                if isinstance(exc, AIError)
                else ("graph_step_limit" if isinstance(exc, GraphRecursionError) else "timeout")
            )
            trace["multiagent"]["errors"].append(code)
            raise AIError(code) from None
        finally:
            trace["multiagent"].update(
                provider_calls=state["budget"].calls,
                model_called=state["budget"].calls > 0,
                planning_operations=state["budget"].planning,
                steps=state["budget"].steps,
                external_provider_calls=(
                    state["budget"].calls if self.provider_kind == "cloudflare_workers_ai" else 0
                ),
                qwen_called=(
                    state["budget"].calls > 0
                    and self.provider_kind == "cloudflare_workers_ai"
                    and "qwen" in (self.model or "").lower()
                ),
            )
