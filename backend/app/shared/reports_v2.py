"""Read-only presentation and bounded authorized figure contracts."""

from typing import Literal

from pydantic import Field

from app.shared.analysis_v2 import ID, SourceRef, V2Model


class DisplayMetricV2(V2Model):
    key: str
    label: str
    formatted: str
    unit: str | None
    reason: str | None


class DisplayTableV2(V2Model):
    id: ID
    title: str
    columns: list[str]
    rows: list[list[str]]


class ResultPresentationV2(V2Model):
    schema_version: Literal["2.0.0"] = "2.0.0"
    result_id: ID
    status_label: str
    technique_label: str
    metrics: list[DisplayMetricV2]
    tables: list[DisplayTableV2]
    interpretation: str | None
    interpretation_metric_keys: list[str]
    interpretation_label: str
    assumptions: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    format_policy: Literal["es-significant-6-v1"] = "es-significant-6-v1"


class ResultFigureDataV2(V2Model):
    id: ID
    kind: Literal["scatter", "paired", "groups", "bars", "metric"]
    x_label: str
    y_label: str
    x: list[float] = Field(max_length=500)
    y: list[float] = Field(max_length=500)
    labels: list[str] = Field(default_factory=list, max_length=500)
    caption: str
    source_metric_keys: list[str] = Field(default_factory=list)
    total_cases: int
    displayed_cases: int
    policy: Literal["persisted-aggregate-v1", "deterministic-complete-cases-500-v1"]
    axis_min: float | None = None
    axis_max: float | None = None


class ResultFiguresV2(V2Model):
    schema_version: Literal["2.0.0"] = "2.0.0"
    result_id: ID
    source_refs: list[SourceRef]
    figures: list[ResultFigureDataV2]
    warnings: list[str]


REPORT_MODELS = (ResultPresentationV2, ResultFiguresV2)
