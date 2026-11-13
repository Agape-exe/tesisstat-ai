"""Composition root for endpoints that require a verified Supabase identity."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import Settings, get_settings
from app.modules.auth.routes import router as auth_router
from app.shared.adapters.supabase_auth import SupabaseIdentityProvider
from app.shared.ports import IdentityProvider


def create_authenticated_app(
    settings: Settings | None = None,
    *,
    identity_provider: IdentityProvider | None = None,
) -> FastAPI:
    settings = settings or get_settings()
    provider = identity_provider or SupabaseIdentityProvider(settings)
    app = FastAPI(title="TesisStat AI", version="0.1.0")
    app.state.identity_provider = provider
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
        allow_credentials=False,
    )

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "service": "tesisstat-api", "version": "0.1.0"}

    app.include_router(auth_router)
    return app
