"""Future Supabase boundaries; these placeholders deliberately perform no I/O."""

from app.core.config import Settings


class SupabaseAdapter:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def read(self, key: str) -> bytes:
        raise NotImplementedError("Supabase Storage is not connected in session 1")

    async def resolve_user(self, access_token: str) -> str:
        raise NotImplementedError("Supabase Auth is not connected in session 1")

    async def get(self, package_id: str, *, owner_id: str) -> dict[str, object]:
        raise NotImplementedError("Supabase persistence is not connected in session 1")
