"""Research-local project drafts, independent of shared methodological contracts."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ProjectDraft(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, frozen=True)

    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=2000)
    university: str | None = Field(default=None, max_length=160)
    faculty: str | None = Field(default=None, max_length=160)
    program: str | None = Field(default=None, max_length=160)
    degree: Literal["bachelor", "master", "doctorate", "other"] | None = None
    academic_year: int | None = Field(default=None, ge=1900, le=2100, strict=True)


class ProjectUpdate(ProjectDraft):
    """Compatible PUT: omitted fields are preserved; only academics accept null."""

    title: str = Field(default="", min_length=1, max_length=200)


class Project(ProjectDraft):
    id: UUID
    status: Literal["draft"] = "draft"
    created_at: datetime
    updated_at: datetime
