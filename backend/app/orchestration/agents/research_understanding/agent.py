from app.orchestration.multiagent.state import AgentState
from app.orchestration.multiagent.tools import ResearchReader
from app.shared.ai_errors import AIError


class ResearchUnderstandingAgent:
    def __init__(self, reader: ResearchReader | None):
        self.reader = reader

    def run(self, state: AgentState) -> dict:
        research = self.reader.build(state["project_id"]) if self.reader else None
        if research is not None and research.project_id != state["project_id"]:
            raise AIError("source_mismatch")
        warnings = (
            [
                f"{s.kind}:{s.status}"
                for s in research.sources
                if s.status
                in {"missing", "draft", "stale", "unverified", "historical", "incomplete"}
            ]
            if research
            else ["sources:missing"]
        )
        state["trace"]["multiagent"]["verified_sources"] = (
            [s.reference() for s in research.sources] if research else []
        )
        return {"research": research, "warnings": warnings}
