"""Local integration records; the six shared contracts remain unchanged."""

import json
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.shared.contracts import AnalysisPlan, AnalysisResult, ResearchPackage


class IntegrationModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PlanRequest(IntegrationModel):
    package_id: str = Field(min_length=1)
    hypothesis_id: str = Field(min_length=1)


class ApprovalRequest(IntegrationModel):
    confirm: Literal[True]
    proposal_token: str = Field(min_length=1)


class RealDataAuthorizationRequest(IntegrationModel):
    """A local, explicit acknowledgement for one exact real-data package."""

    package_id: str = Field(min_length=1)
    dataset_id: str = Field(min_length=1)
    confirm: Literal[True]


class RealDataAuthorizationReceipt(IntegrationModel):
    package_id: str
    dataset_id: str
    source_version: str
    status: Literal["authorized"]


class AuthorizedScatterPoint(IntegrationModel):
    """One complete numeric pair released only by the local authorization flow."""

    x: float
    y: float


class AuthorizedScatterPlot(IntegrationModel):
    """Bounded, plan-scoped observations for an approved association result."""

    x_label: str
    y_label: str
    points: list[AuthorizedScatterPoint]
    complete_pair_count: int
    sampled: bool


class AnalysisRecord(IntegrationModel):
    project_id: UUID
    package: ResearchPackage = Field(exclude=True)
    source_version: str
    proposal_token: str
    plan: AnalysisPlan
    created_at: datetime
    approved_at: datetime | None = None
    invalidated_at: datetime | None = None
    stale_reason: str | None = None
    executable: bool
    limitation: str | None = None
    result: AnalysisResult | None = None

    def storage_json(self) -> str:
        # The snapshot is private persistence, never part of an HTTP response.
        return json.dumps(
            self.model_dump(mode="json") | {"package": self.package.model_dump(mode="json")}
        )
