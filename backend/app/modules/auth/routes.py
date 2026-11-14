from typing import Annotated

from fastapi import APIRouter, Depends

from app.modules.auth.models import SessionIdentity
from app.shared.auth import Principal
from app.shared.auth_http import authenticated_principal

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/me", response_model=SessionIdentity)
def current_session(
    principal: Annotated[Principal, Depends(authenticated_principal)],
) -> SessionIdentity:
    return SessionIdentity(subject=principal.subject, mode=principal.mode)
