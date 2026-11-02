from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel


class Dataset(BaseModel):
    id: UUID
    project_id: UUID
    name: str
    format: Literal["csv", "xlsx"]
    size: int
    row_count: int
    column_count: int
    columns: list[str]
    sheet: str | None = None
    uploaded_at: datetime
    active: bool = False
    warnings: list[str] = []
    source_dataset_id: UUID | None = None


class DatasetPreview(BaseModel):
    columns: list[str]
    rows: list[list[str | None]]
    row_count: int
    column_count: int
    format: Literal["csv", "xlsx"]
    sheet: str | None = None
    warnings: list[str]
