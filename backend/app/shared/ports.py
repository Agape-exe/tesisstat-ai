from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from app.shared.instrument_contracts import InstrumentContext


class LanguageModel(Protocol):
    async def complete(self, prompt: str, *, max_tokens: int) -> str: ...


class ObjectStorage(Protocol):
    async def read(self, key: str) -> bytes: ...


class IdentityProvider(Protocol):
    async def resolve_user(self, access_token: str) -> str: ...


class ResearchRepository(Protocol):
    async def get(self, package_id: str, *, owner_id: str) -> dict[str, object]: ...


class InstrumentContextReader(Protocol):
    """Authorized read port for Statistics to consume InstrumentContext v1.0.0."""

    def get_confirmed_context(
        self,
        project_id: str,
        instrument_id: str,
    ) -> "InstrumentContext": ...
