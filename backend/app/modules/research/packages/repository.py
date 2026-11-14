from typing import Protocol
from uuid import UUID

from app.modules.research.packages.models import StoredPackage


class PackageRepository(Protocol):
    def get(self, project_id: UUID) -> StoredPackage | None: ...
    def save(self, record: StoredPackage, expected_version: int | None) -> bool: ...
    def find_package(self, package_id: str) -> StoredPackage | None: ...
