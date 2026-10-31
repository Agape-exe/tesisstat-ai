"""Configuration-only adapter skeleton. No network or paid fallback."""

from app.core.config import Settings


class CloudflareLanguageModel:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def complete(self, prompt: str, *, max_tokens: int) -> str:
        raise NotImplementedError("Cloudflare integration is scheduled for a later session")
