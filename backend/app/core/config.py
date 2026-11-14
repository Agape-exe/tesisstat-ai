import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "development"
    cors_origins: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:5174",
            "http://127.0.0.1:5174",
            "https://tesisstat-ai.vercel.app",
        ]
    )
    cloudflare_account_id: str = ""
    cloudflare_api_token: str = Field(default="", repr=False)
    cloudflare_model: str = "@cf/qwen/qwen3-30b-a3b-fp8"
    gemini_api_key: str = Field(default="", repr=False)
    gemini_model: str = "gemini-3.5-flash-lite"
    supabase_url: str = ""
    supabase_key: str = ""
    database_url: str = ""
    research_storage_dir: Path = Field(
        default_factory=lambda: Path(os.environ.get("DATA_DIR", ".data/research"))
    )

    @model_validator(mode="before")
    @classmethod
    def populate_environment_and_cors(cls, data: Any) -> Any:
        if isinstance(data, dict):
            # Map ENVIRONMENT -> app_env if app_env not explicitly supplied
            env_val = data.get("ENVIRONMENT") or os.environ.get("ENVIRONMENT")
            if env_val and "app_env" not in data and "APP_ENV" not in data:
                data["app_env"] = env_val.strip().lower()

            # Handle CORS_ORIGINS from env (either JSON array or comma-separated)
            raw_cors = data.get("CORS_ORIGINS") or os.environ.get("CORS_ORIGINS")
            if isinstance(raw_cors, str):
                trimmed = raw_cors.strip()
                if trimmed.startswith("[") and trimmed.endswith("]"):
                    try:
                        data["cors_origins"] = json.loads(trimmed)
                    except Exception:
                        data["cors_origins"] = [
                            o.strip().strip("'\"")
                            for o in trimmed[1:-1].split(",")
                            if o.strip()
                        ]
                else:
                    data["cors_origins"] = [
                        o.strip().strip("'\"") for o in trimmed.split(",") if o.strip()
                    ]
        return data


@lru_cache
def get_settings() -> Settings:
    return Settings()
