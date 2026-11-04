"""Explicit, in-memory authorization for real data in the local development app."""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID


@dataclass
class LocalRealDataAuthorization:
    """Fail-closed grants bound to the exact current project source version.

    This deliberately does not persist grants: restarting the local development
    server revokes them, and a package or source change creates a different key.
    """

    _grants: set[tuple[str, str, str, str]] = field(default_factory=set)

    @staticmethod
    def _key(
        project_id: UUID, package_id: str, dataset_id: str, source_version: str
    ) -> tuple[str, str, str, str]:
        return str(project_id), package_id, dataset_id, source_version

    def grant(
        self, project_id: UUID, package_id: str, dataset_id: str, source_version: str
    ) -> None:
        self._grants.add(self._key(project_id, package_id, dataset_id, source_version))

    def allows(
        self, project_id: UUID, package_id: str, dataset_id: str, source_version: str
    ) -> bool:
        return self._key(project_id, package_id, dataset_id, source_version) in self._grants
