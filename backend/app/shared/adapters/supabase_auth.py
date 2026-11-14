"""Fail-closed Supabase JWT verification through its rotating JWKS."""

import asyncio
from collections.abc import Sequence
from typing import Any
from uuid import UUID

import jwt
from jwt import (
    InvalidTokenError,
    PyJWKClient,
    PyJWKClientConnectionError,
    PyJWKClientError,
    PyJWKSetError,
)

from app.core.config import Settings
from app.shared.auth import AuthenticationError, IdentityProviderUnavailable


class SupabaseIdentityProvider:
    """Resolve a verified Supabase access token to its UUID subject."""

    def __init__(self, settings: Settings, *, jwks_client: Any | None = None) -> None:
        issuer = settings.supabase_jwt_issuer.rstrip("/")
        jwks_url = settings.supabase_jwks_url or (
            f"{issuer}/.well-known/jwks.json" if issuer else ""
        )
        if not issuer or not jwks_url or not settings.supabase_jwt_audience:
            raise ValueError("Supabase JWT issuer, audience and JWKS URL are required")
        algorithms = tuple(settings.supabase_jwt_algorithms)
        if not algorithms or any(value not in {"ES256", "RS256"} for value in algorithms):
            raise ValueError("Supabase JWT algorithms must be an allowlist of ES256 and/or RS256")

        self._issuer = issuer
        self._audience = settings.supabase_jwt_audience
        self._algorithms: Sequence[str] = algorithms
        self._jwks = jwks_client or PyJWKClient(
            jwks_url,
            cache_keys=True,
            max_cached_keys=16,
            cache_jwk_set=True,
            lifespan=settings.supabase_jwks_cache_seconds,
            timeout=settings.supabase_jwks_timeout_seconds,
        )

    async def resolve_user(self, access_token: str) -> str:
        if not access_token or access_token.count(".") != 2:
            raise AuthenticationError("invalid bearer token")
        try:
            header = jwt.get_unverified_header(access_token)
            if header.get("alg") not in self._algorithms or not isinstance(header.get("kid"), str):
                raise AuthenticationError("invalid bearer token")
            signing_key = await asyncio.to_thread(self._jwks.get_signing_key_from_jwt, access_token)
            claims = jwt.decode(
                access_token,
                signing_key.key,
                algorithms=list(self._algorithms),
                audience=self._audience,
                issuer=self._issuer,
                options={"require": ["exp", "sub", "role"]},
            )
        except AuthenticationError:
            raise
        except (PyJWKClientConnectionError, PyJWKSetError) as exc:
            raise IdentityProviderUnavailable("identity provider unavailable") from exc
        except PyJWKClientError as exc:
            if str(exc).startswith("Unable to find a signing key that matches"):
                raise AuthenticationError("invalid bearer token") from exc
            raise IdentityProviderUnavailable("identity provider unavailable") from exc
        except (InvalidTokenError, ValueError, TypeError) as exc:
            raise AuthenticationError("invalid bearer token") from exc

        if claims.get("role") != "authenticated":
            raise AuthenticationError("invalid bearer token")
        try:
            return str(UUID(str(claims["sub"])))
        except (KeyError, TypeError, ValueError) as exc:
            raise AuthenticationError("invalid bearer token") from exc
