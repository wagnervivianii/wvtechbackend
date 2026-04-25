from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.core.rate_limit import rate_limit_client_auth
from app.core.security import require_client_auth
from app.db.session import get_db
from app.schemas.client_auth import (
    ClientAuthMessageResponse,
    ClientAuthTokenResponse,
    ClientFirstAccessRequest,
    ClientForgotPasswordRequest,
    ClientGoogleExchangeRequest,
    ClientGoogleExchangeResponse,
    ClientGoogleStartResponse,
    ClientInvitePreviewResponse,
    ClientLoginRequest,
    ClientMeResponse,
    ClientResetPasswordRequest,
)
from app.services.client_auth import (
    authenticate_client_with_password,
    complete_client_first_access,
    exchange_client_google_auth,
    get_client_me,
    preview_client_invite,
    request_client_password_reset,
    reset_client_password,
    start_client_google_auth,
)

router = APIRouter(prefix='/client/auth', tags=['client-auth'])


@router.get('/invites/{invite_token}', response_model=ClientInvitePreviewResponse)
def get_client_invite_preview(
    invite_token: str,
    db: Session = Depends(get_db),
) -> ClientInvitePreviewResponse:
    return preview_client_invite(db, invite_token)


@router.post('/first-access', response_model=ClientAuthTokenResponse)
def post_client_first_access(
    payload: ClientFirstAccessRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> ClientAuthTokenResponse:
    rate_limit_client_auth(request)
    return complete_client_first_access(db, payload)


@router.post('/login', response_model=ClientAuthTokenResponse)
def post_client_login(
    payload: ClientLoginRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> ClientAuthTokenResponse:
    rate_limit_client_auth(request)
    return authenticate_client_with_password(db, payload)


@router.post('/forgot-password', response_model=ClientAuthMessageResponse)
def post_client_forgot_password(
    payload: ClientForgotPasswordRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> ClientAuthMessageResponse:
    rate_limit_client_auth(request)
    return request_client_password_reset(db, payload)


@router.post('/reset-password', response_model=ClientAuthMessageResponse)
def post_client_reset_password(
    payload: ClientResetPasswordRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> ClientAuthMessageResponse:
    rate_limit_client_auth(request)
    return reset_client_password(db, payload)


@router.get('/google/start', response_model=ClientGoogleStartResponse)
def get_client_google_start(
    redirect_uri: str = Query(..., min_length=1, max_length=2048),
    invite_token: str | None = Query(None, min_length=20, max_length=1024),
) -> ClientGoogleStartResponse:
    return start_client_google_auth(redirect_uri=redirect_uri, invite_token=invite_token)


@router.post('/google/exchange', response_model=ClientGoogleExchangeResponse)
def post_client_google_exchange(
    payload: ClientGoogleExchangeRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> ClientGoogleExchangeResponse:
    rate_limit_client_auth(request)
    return exchange_client_google_auth(db, payload)


@router.get('/me', response_model=ClientMeResponse)
def get_client_auth_me(
    claims: dict[str, object] = Depends(require_client_auth),
    db: Session = Depends(get_db),
) -> ClientMeResponse:
    return get_client_me(db, claims)