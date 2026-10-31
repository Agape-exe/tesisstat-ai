from typing import Protocol


class LanguageModel(Protocol):
    async def complete(self, prompt: str, *, max_tokens: int) -> str: ...


class ObjectStorage(Protocol):
    async def read(self, key: str) -> bytes: ...


class IdentityProvider(Protocol):
    async def resolve_user(self, access_token: str) -> str: ...


class ResearchRepository(Protocol):
    async def get(self, package_id: str, *, owner_id: str) -> dict[str, object]: ...
