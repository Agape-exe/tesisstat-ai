from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "development"
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:5173"])
    cloudflare_account_id: str = ""
    cloudflare_api_token: str = Field(default="", repr=False)
    cloudflare_model: str = "@cf/qwen/qwen3-30b-a3b-fp8"
    gemini_api_key: str = Field(default="", repr=False)
    gemini_model: str = "gemini-3.5-flash"
    supabase_url: str = ""
    supabase_key: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
