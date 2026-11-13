from typing import Literal
from uuid import UUID

from pydantic import BaseModel


class SessionIdentity(BaseModel):
    subject: UUID
    mode: Literal["local", "authenticated"]
