from fastapi import APIRouter, Depends, HTTPException, status

from app.core.config import settings
from app.core.security import (
    create_admin_access_token,
    is_admin_auth_configured,
    require_admin_auth,
    verify_admin_credentials,
)
from app.schemas.admin_auth import (
    AdminLoginRequest,
    AdminLoginResponse,
    AdminMeResponse,
)

router = APIRouter(prefix="/admin/auth", tags=["admin-auth"])


@router.post("/login", response_model=AdminLoginResponse)
def admin_login(payload: AdminLoginRequest) -> AdminLoginResponse:
    if not is_admin_auth_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Autenticação administrativa não configurada no ambiente.",
        )

    if not verify_admin_credentials(payload.username, payload.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuário ou senha inválidos.",
        )

    return AdminLoginResponse(
        access_token=create_admin_access_token(),
        token_type="bearer",
        expires_in=settings.admin_token_ttl_minutes * 60,
        username=settings.admin_username,
    )


@router.get("/me", response_model=AdminMeResponse)
def admin_me(
    claims: dict[str, str | int] = Depends(require_admin_auth),
) -> AdminMeResponse:
    return AdminMeResponse(
        authenticated=True,
        username=str(claims["sub"]),
        role=str(claims["role"]),
    )