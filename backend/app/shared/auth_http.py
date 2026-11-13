"""FastAPI dependency that translates identity failures into stable HTTP errors."""

from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.shared.auth import AuthenticationError, IdentityProviderUnavailable, Principal
from app.shared.ports import IdentityProvider

_bearer = HTTPBearer(auto_error=False)


async def authenticated_principal(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> Principal:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    provider: IdentityProvider | None = getattr(request.app.state, "identity_provider", None)
    if provider is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="identity provider unavailable",
        )
    try:
        subject = await provider.resolve_user(credentials.credentials)
        return Principal(subject=UUID(subject), mode="authenticated")
    except IdentityProviderUnavailable as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="identity provider unavailable",
        ) from exc
    except (AuthenticationError, TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
