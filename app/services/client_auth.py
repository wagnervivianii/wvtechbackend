from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import hashlib
import json
import secrets
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from zoneinfo import ZoneInfo

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.public_url_security import validate_public_redirect_uri
from app.core.security import (
    create_client_access_token,
    create_client_google_state_token,
    decode_client_google_state_token,
    get_password_hash,
    verify_password,
)
from app.models.client_workspace import ClientWorkspace
from app.models.client_workspace_account import ClientWorkspaceAccount
from app.models.client_workspace_invite import ClientWorkspaceInvite
from app.models.client_workspace_password_reset_token import ClientWorkspacePasswordResetToken
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
from app.services.email_notifications import send_email
from app.services.email_templates import build_client_password_reset_email, build_client_password_reset_url


@dataclass(frozen=True, slots=True)
class GoogleProfile:
    subject: str
    email: str
    full_name: str | None
    picture_url: str | None


@dataclass(frozen=True, slots=True)
class AuthenticatedClientContext:
    account: ClientWorkspaceAccount
    workspace: ClientWorkspace



def _now_local() -> datetime:
    return datetime.now(ZoneInfo(settings.app_timezone))



def _normalize_email(value: str) -> str:
    return value.strip().lower()



def _serialize_me_response(account: ClientWorkspaceAccount, workspace: ClientWorkspace) -> ClientMeResponse:
    has_password = bool(account.password_hash)
    google_linked = bool(account.google_subject)
    if has_password and google_linked:
        auth_provider = 'password_google'
    elif google_linked:
        auth_provider = 'google'
    else:
        auth_provider = 'password'

    return ClientMeResponse(
        authenticated=True,
        account_id=account.id,
        workspace_id=workspace.id,
        workspace_status=workspace.workspace_status,
        email=account.email,
        full_name=account.full_name,
        auth_provider=auth_provider,
        has_password=has_password,
        google_linked=google_linked,
        last_login_at=account.last_login_at.isoformat() if account.last_login_at else None,
    )



def _get_workspace_or_404(db: Session, workspace_id: int) -> ClientWorkspace:
    workspace = db.get(ClientWorkspace, workspace_id)
    if workspace is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail='Workspace do cliente não encontrado.',
        )
    return workspace



def _get_account_or_404(db: Session, account_id: int) -> ClientWorkspaceAccount:
    account = db.get(ClientWorkspaceAccount, account_id)
    if account is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail='Conta do cliente não encontrada.',
        )
    return account



def _get_active_account_by_email(db: Session, email: str) -> ClientWorkspaceAccount | None:
    normalized_email = _normalize_email(email)
    return db.scalar(
        select(ClientWorkspaceAccount)
        .where(ClientWorkspaceAccount.email == normalized_email)
        .order_by(ClientWorkspaceAccount.id.desc())
    )



def _get_account_by_google_subject(db: Session, subject: str) -> ClientWorkspaceAccount | None:
    return db.scalar(
        select(ClientWorkspaceAccount)
        .where(ClientWorkspaceAccount.google_subject == subject)
    )



def _find_invite_by_raw_token(db: Session, raw_token: str) -> ClientWorkspaceInvite | None:
    token_hash = hashlib.sha256(raw_token.encode('utf-8')).hexdigest()
    return db.scalar(
        select(ClientWorkspaceInvite)
        .where(ClientWorkspaceInvite.invite_token_hash == token_hash)
    )



def _find_reset_token_by_raw_token(
    db: Session,
    raw_token: str,
) -> ClientWorkspacePasswordResetToken | None:
    token_hash = hashlib.sha256(raw_token.encode('utf-8')).hexdigest()
    return db.scalar(
        select(ClientWorkspacePasswordResetToken)
        .where(ClientWorkspacePasswordResetToken.token_hash == token_hash)
    )



def _is_datetime_expired(value: datetime | None) -> bool:
    if value is None:
        return False
    return value <= _now_local()



def _ensure_invite_can_activate(invite: ClientWorkspaceInvite) -> None:
    if invite.invite_status == 'accepted':
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail='Este convite já foi utilizado para ativar a área do cliente.',
        )
    if invite.invite_status != 'pending':
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail='Este convite não está mais disponível para ativação.',
        )
    if _is_datetime_expired(invite.expires_at):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='O link de ativação expirou. Solicite um novo acesso à equipe da WV Tech Solutions.',
        )



def _consume_invite(db: Session, invite: ClientWorkspaceInvite, workspace: ClientWorkspace) -> None:
    now_local = _now_local()
    invite.invite_status = 'accepted'
    invite.accepted_at = now_local
    workspace.workspace_status = 'activated'
    workspace.activated_at = workspace.activated_at or now_local
    db.add(invite)
    db.add(workspace)



def _touch_login(db: Session, account: ClientWorkspaceAccount) -> None:
    account.last_login_at = _now_local()
    db.add(account)
    db.commit()
    db.refresh(account)



def _build_token_response(account: ClientWorkspaceAccount) -> ClientAuthTokenResponse:
    token = create_client_access_token(
        account_id=account.id,
        workspace_id=account.workspace_id,
        email=account.email,
    )
    has_password = bool(account.password_hash)
    google_linked = bool(account.google_subject)
    if has_password and google_linked:
        auth_provider = 'password_google'
    elif google_linked:
        auth_provider = 'google'
    else:
        auth_provider = 'password'
    return ClientAuthTokenResponse(
        access_token=token,
        expires_in=settings.client_auth_token_ttl_minutes * 60,
        workspace_id=account.workspace_id,
        email=account.email,
        auth_provider=auth_provider,
    )



def preview_client_invite(db: Session, invite_token: str) -> ClientInvitePreviewResponse:
    invite = _find_invite_by_raw_token(db, invite_token)
    if invite is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail='Convite do portal não encontrado.',
        )

    workspace = _get_workspace_or_404(db, invite.workspace_id)
    is_expired = _is_datetime_expired(invite.expires_at)
    can_activate = invite.invite_status == 'pending' and not is_expired

    return ClientInvitePreviewResponse(
        invite_email=invite.invite_email,
        contact_name=workspace.primary_contact_name,
        workspace_status=workspace.workspace_status,
        invite_status=invite.invite_status,
        expires_at=invite.expires_at.isoformat() if invite.expires_at else None,
        accepted_at=invite.accepted_at.isoformat() if invite.accepted_at else None,
        is_expired=is_expired,
        can_activate=can_activate,
    )



def complete_client_first_access(
    db: Session,
    payload: ClientFirstAccessRequest,
) -> ClientAuthTokenResponse:
    invite = _find_invite_by_raw_token(db, payload.invite_token)
    if invite is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail='Link de ativação inválido.',
        )

    _ensure_invite_can_activate(invite)
    workspace = _get_workspace_or_404(db, invite.workspace_id)

    account = _get_active_account_by_email(db, invite.invite_email)
    if account is None:
        account = ClientWorkspaceAccount(
            workspace_id=workspace.id,
            email=_normalize_email(invite.invite_email),
            full_name=workspace.primary_contact_name,
            password_hash=get_password_hash(payload.password),
        )
        db.add(account)
        db.flush()
    else:
        account.workspace_id = workspace.id
        account.email = _normalize_email(invite.invite_email)
        account.full_name = workspace.primary_contact_name
        account.password_hash = get_password_hash(payload.password)
        db.add(account)

    _consume_invite(db, invite, workspace)
    account.last_login_at = _now_local()
    db.add(account)
    db.commit()
    db.refresh(account)

    return _build_token_response(account)



def authenticate_client_with_password(
    db: Session,
    payload: ClientLoginRequest,
) -> ClientAuthTokenResponse:
    account = _get_active_account_by_email(db, payload.email)
    if account is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='E-mail ou senha inválidos.',
        )

    if not account.password_hash:
        if account.google_subject:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail='Esta conta ainda não possui senha. Entre com Google ou solicite a criação de uma senha.',
            )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='Esta conta ainda não possui senha cadastrada. Utilize o link de primeiro acesso.',
        )

    if not verify_password(payload.password, account.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='E-mail ou senha inválidos.',
        )

    _touch_login(db, account)
    return _build_token_response(account)



def _issue_password_reset_token(db: Session, account: ClientWorkspaceAccount) -> str:
    now_local = _now_local()
    raw_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw_token.encode('utf-8')).hexdigest()

    pending_tokens = db.scalars(
        select(ClientWorkspacePasswordResetToken)
        .where(ClientWorkspacePasswordResetToken.account_id == account.id)
        .where(ClientWorkspacePasswordResetToken.used_at.is_(None))
    ).all()
    for token in pending_tokens:
        token.used_at = now_local
        db.add(token)

    reset_token = ClientWorkspacePasswordResetToken(
        account_id=account.id,
        token_hash=token_hash,
        token_type='password_reset',
        expires_at=now_local + timedelta(minutes=settings.client_password_reset_ttl_minutes),
        sent_at=now_local,
    )
    db.add(reset_token)
    db.commit()
    return raw_token



def _send_password_reset_email_best_effort(db: Session, account: ClientWorkspaceAccount) -> None:
    raw_token = _issue_password_reset_token(db=db, account=account)
    reset_url = build_client_password_reset_url(raw_token)
    workspace = _get_workspace_or_404(db, account.workspace_id)
    email_content = build_client_password_reset_email(
        recipient_name=account.full_name or workspace.primary_contact_name,
        reset_url=reset_url,
    )
    send_email(to_email=account.email, content=email_content)



def request_client_password_reset(
    db: Session,
    payload: ClientForgotPasswordRequest,
) -> ClientAuthMessageResponse:
    generic_message = (
        'Se existir uma conta compatível com este e-mail, enviaremos um link para redefinição de senha.'
    )
    account = _get_active_account_by_email(db, payload.email)
    if account is None:
        return ClientAuthMessageResponse(message=generic_message)

    try:
        _send_password_reset_email_best_effort(db, account)
    except Exception:
        return ClientAuthMessageResponse(
            message='Não foi possível enviar o link agora. Tente novamente em instantes.'
        )

    return ClientAuthMessageResponse(message=generic_message)



def reset_client_password(
    db: Session,
    payload: ClientResetPasswordRequest,
) -> ClientAuthMessageResponse:
    reset_token = _find_reset_token_by_raw_token(db, payload.token)
    if reset_token is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='O link de redefinição é inválido ou já foi utilizado.',
        )

    if reset_token.used_at is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='O link de redefinição é inválido ou já foi utilizado.',
        )

    if _is_datetime_expired(reset_token.expires_at):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='O link de redefinição expirou. Solicite um novo envio.',
        )

    account = _get_account_or_404(db, reset_token.account_id)
    account.password_hash = get_password_hash(payload.password)
    account.last_login_at = _now_local()
    reset_token.used_at = _now_local()
    db.add(account)
    db.add(reset_token)
    db.commit()

    return ClientAuthMessageResponse(
        message='Senha atualizada com sucesso. Agora você já pode entrar na área do cliente.'
    )



def get_authenticated_client_context(db: Session, claims: dict[str, object]) -> AuthenticatedClientContext:
    account_id = int(claims.get('sub', 0))
    workspace_id = int(claims.get('workspace_id', 0))
    account = _get_account_or_404(db, account_id)
    workspace = _get_workspace_or_404(db, workspace_id)
    if account.workspace_id != workspace.id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='Sessão do cliente inválida.',
        )
    return AuthenticatedClientContext(account=account, workspace=workspace)



def get_client_me(db: Session, claims: dict[str, object]) -> ClientMeResponse:
    context = get_authenticated_client_context(db, claims)
    return _serialize_me_response(context.account, context.workspace)



def start_client_google_auth(*, redirect_uri: str, invite_token: str | None = None) -> ClientGoogleStartResponse:
    safe_redirect_uri = validate_public_redirect_uri(redirect_uri)
    if not settings.client_google_oauth_client_id or not settings.client_google_oauth_client_secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail='Entrada com Google não configurada no ambiente.',
        )

    state = create_client_google_state_token(
        redirect_uri=safe_redirect_uri,
        invite_token=invite_token,
    )
    query = urlencode(
        {
            'client_id': settings.client_google_oauth_client_id,
            'redirect_uri': safe_redirect_uri,
            'response_type': 'code',
            'scope': settings.client_google_oauth_scope,
            'state': state,
            'prompt': 'select_account',
            'access_type': 'online',
        }
    )
    authorization_url = f'{settings.client_google_oauth_authorize_url}?{query}'
    return ClientGoogleStartResponse(authorization_url=authorization_url, state=state)



def _post_form_json(url: str, data: dict[str, str]) -> dict[str, object]:
    body = urlencode(data).encode('utf-8')
    request = Request(
        url,
        data=body,
        headers={'Content-Type': 'application/x-www-form-urlencoded'},
        method='POST',
    )
    try:
        with urlopen(request, timeout=20) as response:
            return json.loads(response.read().decode('utf-8'))
    except HTTPError as exc:
        payload = exc.read().decode('utf-8', errors='ignore')
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f'Não foi possível validar o retorno do Google. {payload or exc.reason}',
        ) from exc
    except URLError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail='Não foi possível conectar ao Google para concluir a autenticação.',
        ) from exc



def _get_json(url: str, bearer_token: str) -> dict[str, object]:
    request = Request(
        url,
        headers={'Authorization': f'Bearer {bearer_token}'},
        method='GET',
    )
    try:
        with urlopen(request, timeout=20) as response:
            return json.loads(response.read().decode('utf-8'))
    except HTTPError as exc:
        payload = exc.read().decode('utf-8', errors='ignore')
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f'Não foi possível obter os dados do Google. {payload or exc.reason}',
        ) from exc
    except URLError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail='Não foi possível obter os dados do Google.',
        ) from exc



def _exchange_google_code_for_profile(*, code: str, redirect_uri: str) -> GoogleProfile:
    token_payload = _post_form_json(
        settings.client_google_oauth_token_url,
        {
            'code': code,
            'client_id': settings.client_google_oauth_client_id,
            'client_secret': settings.client_google_oauth_client_secret,
            'redirect_uri': redirect_uri,
            'grant_type': 'authorization_code',
        },
    )
    access_token = str(token_payload.get('access_token') or '').strip()
    if not access_token:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail='O Google não retornou um token de acesso válido.',
        )

    profile_payload = _get_json(settings.client_google_oauth_userinfo_url, access_token)
    subject = str(profile_payload.get('sub') or '').strip()
    email = _normalize_email(str(profile_payload.get('email') or '').strip())
    full_name = str(profile_payload.get('name') or '').strip() or None
    picture_url = str(profile_payload.get('picture') or '').strip() or None
    if not subject or not email:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail='O Google não retornou os dados mínimos para autenticação.',
        )
    return GoogleProfile(
        subject=subject,
        email=email,
        full_name=full_name,
        picture_url=picture_url,
    )



def _resolve_account_for_google_login(
    db: Session,
    *,
    profile: GoogleProfile,
    invite_token: str | None,
) -> ClientWorkspaceAccount:
    account = _get_account_by_google_subject(db, profile.subject)
    if account is not None:
        account.google_email = profile.email
        account.google_picture_url = profile.picture_url
        if profile.full_name and not account.full_name:
            account.full_name = profile.full_name
        db.add(account)
        db.flush()
        return account

    if invite_token:
        invite = _find_invite_by_raw_token(db, invite_token)
        if invite is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail='Link de ativação inválido.',
            )
        _ensure_invite_can_activate(invite)
        if _normalize_email(invite.invite_email) != profile.email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail='O e-mail da conta Google não corresponde ao convite enviado para o portal do cliente.',
            )
        workspace = _get_workspace_or_404(db, invite.workspace_id)
        account = _get_active_account_by_email(db, profile.email)
        if account is None:
            account = ClientWorkspaceAccount(
                workspace_id=workspace.id,
                email=profile.email,
                full_name=profile.full_name or workspace.primary_contact_name,
                google_subject=profile.subject,
                google_email=profile.email,
                google_picture_url=profile.picture_url,
            )
            db.add(account)
            db.flush()
        else:
            account.workspace_id = workspace.id
            account.full_name = account.full_name or profile.full_name or workspace.primary_contact_name
            account.google_subject = profile.subject
            account.google_email = profile.email
            account.google_picture_url = profile.picture_url
            db.add(account)
            db.flush()

        _consume_invite(db, invite, workspace)
        db.add(account)
        db.flush()
        return account

    account = _get_active_account_by_email(db, profile.email)
    if account is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail='Não encontramos uma área do cliente vinculada a este e-mail. Use o link enviado pela WV Tech Solutions para ativar seu acesso.',
        )

    account.google_subject = profile.subject
    account.google_email = profile.email
    account.google_picture_url = profile.picture_url
    account.full_name = account.full_name or profile.full_name
    db.add(account)
    db.flush()
    return account



def exchange_client_google_auth(
    db: Session,
    payload: ClientGoogleExchangeRequest,
) -> ClientGoogleExchangeResponse:
    state_payload = decode_client_google_state_token(payload.state)
    expected_redirect_uri = validate_public_redirect_uri(str(state_payload.get('redirect_uri') or '').strip())
    safe_redirect_uri = validate_public_redirect_uri(payload.redirect_uri)
    if expected_redirect_uri != safe_redirect_uri:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='State inválido ou expirado.',
        )

    invite_token = state_payload.get('invite_token')
    invite_value = str(invite_token).strip() if invite_token else None
    profile = _exchange_google_code_for_profile(code=payload.code, redirect_uri=safe_redirect_uri)
    account = _resolve_account_for_google_login(
        db,
        profile=profile,
        invite_token=invite_value,
    )
    account.last_login_at = _now_local()
    db.add(account)
    db.commit()
    db.refresh(account)

    token_response = _build_token_response(account)
    return ClientGoogleExchangeResponse(
        **token_response.model_dump(),
        avatar_url=profile.picture_url,
    )