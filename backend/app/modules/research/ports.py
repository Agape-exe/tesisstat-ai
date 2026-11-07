from typing import Protocol

from app.shared.contracts import ResearchPackage
from app.shared.instrument_contracts import InstrumentContext
from app.shared.ports import InstrumentContextReader


class ResearchPackageReader(Protocol):
    """Statistics consumes this port, never Research's internal storage implementation."""

    def get_package(self, package_id: str) -> ResearchPackage: ...


__all__ = ["InstrumentContext", "InstrumentContextReader", "ResearchPackageReader"]
