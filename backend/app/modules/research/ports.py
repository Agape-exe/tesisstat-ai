from typing import Protocol

from app.modules.research.instrument.contracts import InstrumentContext
from app.shared.contracts import ResearchPackage


class ResearchPackageReader(Protocol):
    """Statistics consumes this port, never Research's internal storage implementation."""

    def get_package(self, package_id: str) -> ResearchPackage: ...


class InstrumentContextReader(Protocol):
    """Authorized read port for Statistics to consume InstrumentContext v1.0.0."""

    def get_confirmed_context(
        self,
        project_id: str,
        instrument_id: str,
    ) -> InstrumentContext: ...
