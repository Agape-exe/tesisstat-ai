from typing import Protocol

from app.shared.contracts import ResearchPackage


class ResearchPackageReader(Protocol):
    """Statistics consumes this port, never Research's internal storage implementation."""

    def get_package(self, package_id: str) -> ResearchPackage: ...
