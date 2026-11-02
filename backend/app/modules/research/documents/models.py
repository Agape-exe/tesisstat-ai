from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel


class Document(BaseModel):
    id: UUID
    project_id: UUID
    name: str
    format: Literal["pdf", "docx"]
    size: int
    uploaded_at: datetime
