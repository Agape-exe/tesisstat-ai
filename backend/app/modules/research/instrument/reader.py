"""Authorized read adapter for Statistics to consume InstrumentContext v1.0.0."""

from typing import Protocol
from uuid import UUID

from app.modules.research.instrument.contracts import InstrumentContext
from app.modules.research.instrument.repository import (
    InstrumentNotConfirmedError,
    InstrumentNotFound,
    InstrumentStaleError,
)
from app.modules.research.instrument.service import InstrumentService


class InstrumentContextReader(Protocol):
    """Statistics consumes this port, never Research's internal storage implementation."""

    def get_confirmed_context(
        self,
        project_id: str,
        instrument_id: str,
    ) -> InstrumentContext: ...


class ResearchInstrumentContextReader:
    def __init__(self, service: InstrumentService):
        self.service = service

    def get_confirmed_context(
        self,
        project_id: str,
        instrument_id: str,
    ) -> InstrumentContext:
        try:
            proj_uuid = UUID(project_id)
            inst_uuid = UUID(instrument_id)
        except (ValueError, TypeError) as exc:
            raise InstrumentNotFound(
                "Los identificadores de proyecto e instrumento deben ser UUID válidos."
            ) from exc

        instrument = self.service.get(proj_uuid, inst_uuid)
        if instrument.project_id != proj_uuid:
            raise InstrumentNotFound("El instrumento no pertenece al proyecto especificado.")

        if instrument.status != "reviewed" or instrument.confirmation.state != "confirmed":
            raise InstrumentNotConfirmedError(
                f"El instrumento '{instrument_id}' no está revisado y confirmado para análisis."
            )

        is_stale, reasons = self.service.check_stale(proj_uuid, inst_uuid)
        if is_stale or instrument.status == "stale":
            raise InstrumentStaleError(
                f"El instrumento '{instrument_id}' está desactualizado respecto a sus fuentes: "
                f"{', '.join(reasons)}",
                reasons=reasons,
            )

        if instrument.dataset_mapping is not None:
            if (
                instrument.dataset_mapping.status != "confirmed"
                or instrument.dataset_mapping.confirmation.state != "confirmed"
            ):
                raise InstrumentNotConfirmedError(
                    f"El mapeo de datos del instrumento '{instrument_id}' no está confirmado."
                )

        return instrument
