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
    gemini_model: str = "gemini-3.5-flash-lite"
    supabase_url: str = ""
    supabase_key: str = ""
    supabase_jwt_issuer: str = ""
    supabase_jwt_audience: str = "authenticated"
    supabase_jwt_algorithms: list[str] = Field(default_factory=lambda: ["ES256", "RS256"])
    supabase_jwks_url: str = ""
    supabase_jwks_cache_seconds: int = Field(default=300, ge=30, le=3600)
    supabase_jwks_timeout_seconds: float = Field(default=5.0, ge=0.5, le=30.0)


@lru_cache
def get_settings() -> Settings:
    return Settings()
