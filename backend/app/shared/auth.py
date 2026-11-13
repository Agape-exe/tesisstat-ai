"""Provider-independent identity and project-access contracts."""

from dataclasses import dataclass
from typing import Literal, Protocol
from uuid import UUID


class AuthenticationError(Exception):
    """The request did not contain a valid end-user identity."""


class IdentityProviderUnavailable(Exception):
    """Identity could not be verified because its provider is unavailable."""


class ProjectNotFound(Exception):
    """A project is missing or is not visible to the current principal."""


@dataclass(frozen=True, slots=True)
class Principal:
    subject: UUID
    mode: Literal["local", "authenticated"]


@dataclass(frozen=True, slots=True)
class AuthorizedProject:
    id: UUID
    owner_id: UUID | None
    mode: Literal["local", "authenticated"]


@dataclass(frozen=True, slots=True)
class ProjectOwner:
    id: UUID
    owner_id: UUID | None


class ProjectOwnership(Protocol):
    def find_owner(self, project_id: UUID) -> ProjectOwner | None: ...

    def list_owned(self, owner_id: UUID) -> list[UUID]: ...


class ProjectAccess:
    """Create immutable project scopes without revealing foreign ownership."""

    def __init__(self, ownership: ProjectOwnership) -> None:
        self._ownership = ownership

    def require(self, principal: Principal, project_id: UUID) -> AuthorizedProject:
        project = self._ownership.find_owner(project_id)
        if project is None:
            raise ProjectNotFound("project not found")
        owner_id = project.owner_id
        if principal.mode == "authenticated" and owner_id != principal.subject:
            raise ProjectNotFound("project not found")
        if principal.mode == "local" and owner_id not in (None, principal.subject):
            raise ProjectNotFound("project not found")
        return AuthorizedProject(id=project_id, owner_id=owner_id, mode=principal.mode)

    def list_owned(self, principal: Principal) -> list[AuthorizedProject]:
        return [
            AuthorizedProject(id=project_id, owner_id=principal.subject, mode=principal.mode)
            for project_id in self._ownership.list_owned(principal.subject)
        ]
