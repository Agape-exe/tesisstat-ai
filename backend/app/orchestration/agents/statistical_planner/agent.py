from app.orchestration.multiagent.state import AgentState
from app.orchestration.multiagent.tools import PlanningReader, clarification
from app.shared.ai_errors import AIError


class StatisticalPlanningAgent:
    def __init__(self, reader: PlanningReader | None):
        self.reader = reader

    def run(self, state: AgentState) -> dict:
        budget = state["budget"]
        if budget.planning >= budget.max_planning:
            raise AIError("planning_limit")
        budget.planning += 1
        research = state["research"]
        planning = (
            self.reader.inspect(state["project_id"], research, state["content"])
            if self.reader and research
            else clarification("Faltan fuentes verificadas para planificar.")
        )
        return {"planning": planning}
