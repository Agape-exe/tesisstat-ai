"""Repository interface and domain exceptions for research instruments."""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from app.modules.research.instrument.contracts import InstrumentContext


class InstrumentError(Exception):
    """Base error for instrument repository operations."""


class InstrumentNotFound(InstrumentError):
    """Raised when an instrument does not exist or does not belong to the project."""


class InstrumentConflict(InstrumentError):
    """Raised on optimistic locking or concurrency conflicts."""


class InstrumentValidationError(InstrumentError):
    """Raised when an instrument violates methodological or data integrity rules."""


class InstrumentStaleError(InstrumentError):
    """Raised when an instrument or its mappings are outdated compared to current sources."""

    def __init__(self, message: str, reasons: list[str] | None = None) -> None:
        super().__init__(message)
        self.reasons = reasons or []


class InstrumentNotConfirmedError(InstrumentError):
    """Raised when trying to read or access an unconfirmed instrument via authorized ports."""


class InstrumentRepository(Protocol):
    def create(self, instrument: InstrumentContext) -> InstrumentContext: ...

    def get(
        self,
        project_id: UUID,
        instrument_id: UUID,
        version: int | None = None,
    ) -> InstrumentContext | None: ...

    def list(self, project_id: UUID) -> list[InstrumentContext]: ...

    def update(
        self,
        instrument: InstrumentContext,
        expected_version: int,
    ) -> InstrumentContext: ...

    def get_history(
        self,
        project_id: UUID,
        instrument_id: UUID,
    ) -> list[InstrumentContext]: ...
