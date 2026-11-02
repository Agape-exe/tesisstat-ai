from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

OperationType = Literal[
    "drop_duplicates",
    "drop_missing",
    "replace_missing",
    "drop_columns",
    "rename_column",
    "trim",
    "to_numeric",
]


class Operation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: OperationType
    columns: list[str] = Field(default_factory=list, max_length=200)
    column: str | None = None
    new_name: str | None = None
    value: str | None = None
    missing_markers: list[Literal["NA", "N/A", "null", "none"]] = Field(default_factory=list)
    empty_is_missing: bool = True


class Plan(BaseModel):
    model_config = ConfigDict(extra="forbid")
    operations: list[Operation] = Field(min_length=1, max_length=20)


class OperationSummary(BaseModel):
    type: OperationType
    rows_removed: int = 0
    cells_changed: int = 0
    columns_removed: list[str] = []
    rename: dict[str, str] = {}


class PreparationPreview(BaseModel):
    preview_id: UUID
    plan_hash: str
    source_sha256: str
    rule_version: str
    expires_at: datetime
    original_rows: int
    result_rows: int
    original_columns: list[str]
    result_columns: list[str]
    rows_removed: int
    cells_changed: int
    warnings: list[str]
    rows: list[list[str | None]]
    operations: list[OperationSummary]


class ApplyRequest(BaseModel):
    plan: Plan
    preview_id: UUID
    plan_hash: str
    confirm: Literal[True]


class PreparationRecord(BaseModel):
    preview_id: UUID
    project_id: UUID
    source_id: UUID
    result_id: UUID
    prepared_at: datetime
    plan: Plan
    source_sha256: str
    rule_version: str
    original_rows: int
    result_rows: int
    original_columns: list[str]
    result_columns: list[str]
    rows_removed: int
    cells_changed: int
    warnings: list[str]
    operations: list[OperationSummary]
