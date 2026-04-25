from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.access_control import ensure_workspace_accepts_admin_lifecycle_change
from app.core.config import settings
from app.models.client_workspace import ClientWorkspace
from app.models.client_workspace_invite import ClientWorkspaceInvite
from app.models.client_workspace_meeting import ClientWorkspaceMeeting
from app.schemas.admin_client_workspaces import (
    AdminClientWorkspaceLifecycleRequest,
    AdminClientWorkspaceLifecycleResponse,
)

WORKSPACE_STATUS_ACTIVATED = 'activated'
WORKSPACE_STATUS_SUSPENDED = 'suspended'
WORKSPACE_STATUS_ARCHIVED = 'archived'
INVITE_STATUS_REVOKED = 'revoked'


def _now_local() -> datetime:
    return datetime.now(ZoneInfo(settings.app_timezone))


def _get_workspace_or_404(db: Session, workspace_id: int) -> ClientWorkspace:
    workspace = db.get(ClientWorkspace, workspace_id)
    if workspace is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Workspace do cliente não encontrado.')
    return workspace


def _append_lifecycle_note(*, current_notes: str | None, action: str, reason: str | None) -> str:
    timestamp = _now_local().strftime('%d/%m/%Y %H:%M:%S')
    clean_reason = (reason or 'Sem motivo informado.').strip()
    lifecycle_note = f'[{timestamp}] Ciclo de vida: {action}. Motivo: {clean_reason}'
    if not current_notes:
        return lifecycle_note
    return f'{current_notes.rstrip()}\n{lifecycle_note}'


def _revoke_pending_invites(db: Session, workspace_id: int) -> int:
    invites = db.scalars(
        select(ClientWorkspaceInvite)
        .where(ClientWorkspaceInvite.workspace_id == workspace_id)
        .where(ClientWorkspaceInvite.invite_status == 'pending')
    ).all()
    now_local = _now_local()
    for invite in invites:
        invite.invite_status = INVITE_STATUS_REVOKED
        invite.expires_at = now_local
        db.add(invite)
    return len(invites)


def _hide_client_meetings(db: Session, workspace_id: int) -> int:
    meetings = db.scalars(
        select(ClientWorkspaceMeeting)
        .where(ClientWorkspaceMeeting.workspace_id == workspace_id)
        .where(ClientWorkspaceMeeting.is_visible_to_client.is_(True))
    ).all()
    for meeting in meetings:
        meeting.is_visible_to_client = False
        db.add(meeting)
    return len(meetings)


def _build_lifecycle_response(
    *,
    workspace_id: int,
    previous_status: str,
    workspace_status: str,
    pending_invites_revoked: int,
    visible_meetings_hidden: int,
    message: str,
) -> AdminClientWorkspaceLifecycleResponse:
    return AdminClientWorkspaceLifecycleResponse(
        workspace_id=workspace_id,
        previous_status=previous_status,
        workspace_status=workspace_status,
        client_access_revoked=workspace_status in {WORKSPACE_STATUS_SUSPENDED, WORKSPACE_STATUS_ARCHIVED},
        pending_invites_revoked=pending_invites_revoked,
        visible_meetings_hidden=visible_meetings_hidden,
        admin_history_preserved=True,
        message=message,
    )


def suspend_client_workspace(
    db: Session,
    *,
    workspace_id: int,
    payload: AdminClientWorkspaceLifecycleRequest,
) -> AdminClientWorkspaceLifecycleResponse:
    workspace = _get_workspace_or_404(db, workspace_id)
    ensure_workspace_accepts_admin_lifecycle_change(workspace)
    previous_status = workspace.workspace_status
    revoked_count = _revoke_pending_invites(db, workspace.id)
    hidden_count = _hide_client_meetings(db, workspace.id)
    workspace.workspace_status = WORKSPACE_STATUS_SUSPENDED
    workspace.portal_notes = _append_lifecycle_note(current_notes=workspace.portal_notes, action='workspace suspenso', reason=payload.reason)
    db.add(workspace)
    db.commit()
    return _build_lifecycle_response(
        workspace_id=workspace.id,
        previous_status=previous_status,
        workspace_status=workspace.workspace_status,
        pending_invites_revoked=revoked_count,
        visible_meetings_hidden=hidden_count,
        message='Workspace suspenso. O cliente não consegue acessar o portal até reativação.',
    )


def archive_client_workspace(
    db: Session,
    *,
    workspace_id: int,
    payload: AdminClientWorkspaceLifecycleRequest,
) -> AdminClientWorkspaceLifecycleResponse:
    workspace = _get_workspace_or_404(db, workspace_id)
    ensure_workspace_accepts_admin_lifecycle_change(workspace)
    previous_status = workspace.workspace_status
    revoked_count = _revoke_pending_invites(db, workspace.id)
    hidden_count = _hide_client_meetings(db, workspace.id)
    workspace.workspace_status = WORKSPACE_STATUS_ARCHIVED
    workspace.portal_notes = _append_lifecycle_note(current_notes=workspace.portal_notes, action='workspace arquivado', reason=payload.reason)
    db.add(workspace)
    db.commit()
    return _build_lifecycle_response(
        workspace_id=workspace.id,
        previous_status=previous_status,
        workspace_status=workspace.workspace_status,
        pending_invites_revoked=revoked_count,
        visible_meetings_hidden=hidden_count,
        message='Workspace arquivado. Histórico preservado para o admin e acesso do cliente revogado.',
    )


def reactivate_client_workspace(
    db: Session,
    *,
    workspace_id: int,
    payload: AdminClientWorkspaceLifecycleRequest,
) -> AdminClientWorkspaceLifecycleResponse:
    workspace = _get_workspace_or_404(db, workspace_id)
    if workspace.workspace_status != WORKSPACE_STATUS_SUSPENDED:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail='Somente workspaces suspensos podem ser reativados por este fluxo.')
    previous_status = workspace.workspace_status
    workspace.workspace_status = WORKSPACE_STATUS_ACTIVATED
    workspace.portal_notes = _append_lifecycle_note(current_notes=workspace.portal_notes, action='workspace reativado', reason=payload.reason)
    db.add(workspace)
    db.commit()
    return _build_lifecycle_response(
        workspace_id=workspace.id,
        previous_status=previous_status,
        workspace_status=workspace.workspace_status,
        pending_invites_revoked=0,
        visible_meetings_hidden=0,
        message='Workspace reativado. O cliente volta a acessar o portal com credenciais válidas.',
    )
