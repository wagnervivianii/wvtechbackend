from __future__ import annotations

from typing import Any

from fastapi import HTTPException, status

from app.models.client_workspace import ClientWorkspace
from app.models.client_workspace_account import ClientWorkspaceAccount

ACTIVE_CLIENT_WORKSPACE_STATUSES = {'activated'}
INVITABLE_CLIENT_WORKSPACE_STATUSES = {'provisioned', 'activated'}


def _generic_invalid_session() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail='Sessão do cliente inválida.',
    )


def parse_positive_int_claim(claims: dict[str, Any], key: str) -> int:
    try:
        value = int(claims.get(key, 0))
    except (TypeError, ValueError) as exc:
        raise _generic_invalid_session() from exc

    if value <= 0:
        raise _generic_invalid_session()

    return value


def ensure_client_token_matches_account(
    *,
    claims: dict[str, Any],
    account: ClientWorkspaceAccount,
    workspace: ClientWorkspace,
) -> None:
    token_account_id = parse_positive_int_claim(claims, 'sub')
    token_workspace_id = parse_positive_int_claim(claims, 'workspace_id')
    token_email = str(claims.get('email') or '').strip().lower()

    if token_account_id != account.id:
        raise _generic_invalid_session()

    if token_workspace_id != workspace.id:
        raise _generic_invalid_session()

    if account.workspace_id != workspace.id:
        raise _generic_invalid_session()

    if token_email and token_email != account.email.strip().lower():
        raise _generic_invalid_session()


def ensure_client_workspace_is_active(workspace: ClientWorkspace) -> None:
    if workspace.workspace_status not in ACTIVE_CLIENT_WORKSPACE_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail='Área do cliente indisponível no momento.',
        )


def ensure_workspace_accepts_invite_activation(workspace: ClientWorkspace) -> None:
    if workspace.workspace_status not in INVITABLE_CLIENT_WORKSPACE_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail='Este workspace não está disponível para ativação.',
        )
