from __future__ import annotations

from datetime import datetime, timedelta
import hashlib
import secrets
from zoneinfo import ZoneInfo

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.booking_request import BookingRequest
from app.models.client_workspace import ClientWorkspace
from app.models.client_workspace_account import ClientWorkspaceAccount
from app.models.client_workspace_invite import ClientWorkspaceInvite
from app.models.client_workspace_meeting import ClientWorkspaceMeeting
from app.schemas.admin_client_workspaces import (
    AdminClientWorkspaceAccountItem,
    AdminClientWorkspaceDetailResponse,
    AdminClientWorkspaceDriveFolderItem,
    AdminClientWorkspaceDriveInfo,
    AdminClientWorkspaceInviteItem,
    AdminClientWorkspaceInviteRefreshRequest,
    AdminClientWorkspaceListResponse,
    AdminClientWorkspaceMeetingItem,
    AdminClientWorkspaceProvisionRequest,
    AdminClientWorkspaceSummaryItem,
)
from app.services.client_workspace_artifacts import (
    attach_admin_artifacts_to_meeting_item,
    auto_sync_workspace_pending_google_artifacts_best_effort,
)
from app.services.email_templates import build_client_setup_url
from app.services.google_drive import (
    GoogleDriveIntegrationError,
    GoogleDriveIntegrationNotConfiguredError,
    GoogleDriveWorkspaceFolders,
    ensure_client_workspace_drive_folders,
    is_google_drive_workspace_storage_configured,
)


DRIVE_PENDING_CONFIGURATION_STATUS = 'pending_configuration'
DRIVE_READY_STATUS = 'ready'
DRIVE_ERROR_STATUS = 'error'


def _now_local() -> datetime:
    return datetime.now(ZoneInfo(settings.app_timezone))


def _get_booking_or_404(db: Session, booking_id: int) -> BookingRequest:
    booking = db.get(BookingRequest, booking_id)
    if booking is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail='Solicitação de reunião não encontrada.',
        )
    return booking


def _build_meeting_label(booking: BookingRequest) -> str:
    start_text = booking.start_time.strftime('%H:%M') if booking.start_time else None
    end_text = booking.end_time.strftime('%H:%M') if booking.end_time else None

    if booking.booking_date and start_text and end_text:
        return f"{booking.booking_date.strftime('%d/%m/%Y')} • {start_text} às {end_text}"

    if booking.booking_date:
        return booking.booking_date.strftime('%d/%m/%Y')

    return f'Solicitação #{booking.id}'


def _serialize_invite(invite: ClientWorkspaceInvite) -> AdminClientWorkspaceInviteItem:
    return AdminClientWorkspaceInviteItem(
        id=invite.id,
        invite_email=invite.invite_email,
        invite_status=invite.invite_status,
        expires_at=invite.expires_at.isoformat() if invite.expires_at else None,
        sent_at=invite.sent_at.isoformat() if invite.sent_at else None,
        accepted_at=invite.accepted_at.isoformat() if invite.accepted_at else None,
        created_at=invite.created_at.isoformat(),
    )


def _serialize_meeting(db: Session, meeting: ClientWorkspaceMeeting) -> AdminClientWorkspaceMeetingItem:
    item = AdminClientWorkspaceMeetingItem(
        id=meeting.id,
        booking_request_id=meeting.booking_request_id,
        meeting_label=meeting.meeting_label,
        meet_url=meeting.meet_url,
        recording_url=meeting.recording_url,
        recording_provider=meeting.recording_provider,
        has_transcript=bool(meeting.transcript_text or meeting.transcript_summary),
        transcript_summary=meeting.transcript_summary,
        transcript_text=meeting.transcript_text,
        meeting_notes=meeting.meeting_notes,
        meeting_started_at=(meeting.meeting_started_at.isoformat() if meeting.meeting_started_at else None),
        meeting_ended_at=(meeting.meeting_ended_at.isoformat() if meeting.meeting_ended_at else None),
        is_visible_to_client=meeting.is_visible_to_client,
        synced_from_booking_at=(meeting.synced_from_booking_at.isoformat() if meeting.synced_from_booking_at else None),
        artifacts=[],
    )
    return attach_admin_artifacts_to_meeting_item(db, item)


def _serialize_account(account: ClientWorkspaceAccount | None) -> AdminClientWorkspaceAccountItem | None:
    if account is None:
        return None

    has_password = bool(account.password_hash)
    google_linked = bool(account.google_subject)
    if has_password and google_linked:
        auth_provider = 'password_google'
    elif google_linked:
        auth_provider = 'google'
    else:
        auth_provider = 'password'

    return AdminClientWorkspaceAccountItem(
        id=account.id,
        email=account.email,
        full_name=account.full_name,
        has_password=has_password,
        google_linked=google_linked,
        auth_provider=auth_provider,
        google_picture_url=account.google_picture_url,
        last_login_at=account.last_login_at.isoformat() if account.last_login_at else None,
        created_at=account.created_at.isoformat(),
    )


def _serialize_drive_folder(
    *,
    folder_id: str | None,
    folder_name: str | None,
    folder_url: str | None,
) -> AdminClientWorkspaceDriveFolderItem | None:
    if not folder_id:
        return None

    return AdminClientWorkspaceDriveFolderItem(
        folder_id=folder_id,
        folder_name=folder_name or 'Pasta Google Drive',
        web_view_link=folder_url,
    )


def _serialize_drive_info(workspace: ClientWorkspace) -> AdminClientWorkspaceDriveInfo:
    return AdminClientWorkspaceDriveInfo(
        sync_status=workspace.drive_sync_status,
        sync_error=workspace.drive_sync_error,
        synced_at=workspace.drive_synced_at.isoformat() if workspace.drive_synced_at else None,
        root=_serialize_drive_folder(
            folder_id=workspace.drive_root_folder_id,
            folder_name=workspace.drive_root_folder_name,
            folder_url=workspace.drive_root_folder_url,
        ),
        meet_artifacts=_serialize_drive_folder(
            folder_id=workspace.drive_meet_artifacts_folder_id,
            folder_name=workspace.drive_meet_artifacts_folder_name,
            folder_url=workspace.drive_meet_artifacts_folder_url,
        ),
        client_uploads=_serialize_drive_folder(
            folder_id=workspace.drive_client_uploads_folder_id,
            folder_name=workspace.drive_client_uploads_folder_name,
            folder_url=workspace.drive_client_uploads_folder_url,
        ),
        generated_documents=_serialize_drive_folder(
            folder_id=workspace.drive_generated_documents_folder_id,
            folder_name=workspace.drive_generated_documents_folder_name,
            folder_url=workspace.drive_generated_documents_folder_url,
        ),
        archive=_serialize_drive_folder(
            folder_id=workspace.drive_archive_folder_id,
            folder_name=workspace.drive_archive_folder_name,
            folder_url=workspace.drive_archive_folder_url,
        ),
    )


def _load_workspace_account(db: Session, workspace_id: int) -> ClientWorkspaceAccount | None:
    return db.scalar(
        select(ClientWorkspaceAccount)
        .where(ClientWorkspaceAccount.workspace_id == workspace_id)
    )


def _load_workspace_meetings(db: Session, workspace_id: int) -> list[ClientWorkspaceMeeting]:
    return db.scalars(
        select(ClientWorkspaceMeeting)
        .where(ClientWorkspaceMeeting.workspace_id == workspace_id)
        .order_by(ClientWorkspaceMeeting.created_at.desc(), ClientWorkspaceMeeting.id.desc())
    ).all()


def _load_workspace_invites(db: Session, workspace_id: int) -> list[ClientWorkspaceInvite]:
    return db.scalars(
        select(ClientWorkspaceInvite)
        .where(ClientWorkspaceInvite.workspace_id == workspace_id)
        .order_by(ClientWorkspaceInvite.created_at.desc(), ClientWorkspaceInvite.id.desc())
    ).all()


def _find_workspace_for_contact(db: Session, booking: BookingRequest) -> ClientWorkspace | None:
    return db.scalar(
        select(ClientWorkspace)
        .where(ClientWorkspace.primary_contact_email == booking.email)
        .where(ClientWorkspace.primary_contact_phone == booking.phone)
        .order_by(ClientWorkspace.created_at.desc(), ClientWorkspace.id.desc())
    )


def _workspace_drive_ready(workspace: ClientWorkspace) -> bool:
    return bool(
        workspace.drive_root_folder_id
        and workspace.drive_meet_artifacts_folder_id
        and workspace.drive_client_uploads_folder_id
        and workspace.drive_generated_documents_folder_id
        and workspace.drive_archive_folder_id
    )


def _apply_drive_folders_to_workspace(
    *,
    workspace: ClientWorkspace,
    folders: GoogleDriveWorkspaceFolders,
) -> None:
    workspace.drive_root_folder_id = folders.root.folder_id
    workspace.drive_root_folder_name = folders.root.folder_name
    workspace.drive_root_folder_url = folders.root.web_view_link
    workspace.drive_meet_artifacts_folder_id = folders.meet_artifacts.folder_id
    workspace.drive_meet_artifacts_folder_name = folders.meet_artifacts.folder_name
    workspace.drive_meet_artifacts_folder_url = folders.meet_artifacts.web_view_link
    workspace.drive_client_uploads_folder_id = folders.client_uploads.folder_id
    workspace.drive_client_uploads_folder_name = folders.client_uploads.folder_name
    workspace.drive_client_uploads_folder_url = folders.client_uploads.web_view_link
    workspace.drive_generated_documents_folder_id = folders.generated_documents.folder_id
    workspace.drive_generated_documents_folder_name = folders.generated_documents.folder_name
    workspace.drive_generated_documents_folder_url = folders.generated_documents.web_view_link
    workspace.drive_archive_folder_id = folders.archive.folder_id
    workspace.drive_archive_folder_name = folders.archive.folder_name
    workspace.drive_archive_folder_url = folders.archive.web_view_link
    workspace.drive_sync_status = DRIVE_READY_STATUS
    workspace.drive_sync_error = None
    workspace.drive_synced_at = _now_local()


def _mark_workspace_drive_pending_configuration(
    *,
    db: Session,
    workspace: ClientWorkspace,
    message: str,
) -> None:
    if _workspace_drive_ready(workspace):
        return
    workspace.drive_sync_status = DRIVE_PENDING_CONFIGURATION_STATUS
    workspace.drive_sync_error = message
    db.add(workspace)
    db.flush()


def _mark_workspace_drive_error(
    *,
    db: Session,
    workspace: ClientWorkspace,
    message: str,
) -> None:
    workspace.drive_sync_status = DRIVE_ERROR_STATUS
    workspace.drive_sync_error = message
    db.add(workspace)
    db.flush()


def _ensure_workspace_drive_structure(
    *,
    db: Session,
    workspace: ClientWorkspace,
    raise_on_failure: bool,
) -> bool:
    if _workspace_drive_ready(workspace):
        if workspace.drive_sync_status != DRIVE_READY_STATUS:
            workspace.drive_sync_status = DRIVE_READY_STATUS
            workspace.drive_sync_error = None
            if workspace.drive_synced_at is None:
                workspace.drive_synced_at = _now_local()
            db.add(workspace)
            db.flush()
        return True

    if not is_google_drive_workspace_storage_configured():
        message = (
            'Estrutura Google Drive do cliente ainda não configurada. '
            'Defina GOOGLE_DRIVE_CLIENTS_ROOT_FOLDER_ID e mantenha as credenciais Google válidas.'
        )
        _mark_workspace_drive_pending_configuration(db=db, workspace=workspace, message=message)
        if raise_on_failure:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=message,
            )
        return False

    try:
        folders = ensure_client_workspace_drive_folders(
            workspace_id=workspace.id,
            primary_contact_name=workspace.primary_contact_name,
            existing_root_folder_id=workspace.drive_root_folder_id,
        )
    except GoogleDriveIntegrationNotConfiguredError as exc:
        message = str(exc)
        _mark_workspace_drive_pending_configuration(db=db, workspace=workspace, message=message)
        if raise_on_failure:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=message,
            ) from exc
        return False
    except GoogleDriveIntegrationError as exc:
        message = str(exc)
        _mark_workspace_drive_error(db=db, workspace=workspace, message=message)
        if raise_on_failure:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f'Não foi possível sincronizar a estrutura do Google Drive do cliente. {message}',
            ) from exc
        return False

    _apply_drive_folders_to_workspace(workspace=workspace, folders=folders)
    db.add(workspace)
    db.flush()
    return True


def _ensure_workspace(db: Session, booking: BookingRequest, portal_notes: str | None) -> ClientWorkspace:
    workspace = _find_workspace_for_contact(db, booking)

    if workspace is None:
        workspace = ClientWorkspace(
            source_booking_request_id=booking.id,
            primary_contact_name=booking.name,
            primary_contact_email=booking.email,
            primary_contact_phone=booking.phone,
            workspace_status='provisioned',
            portal_notes=portal_notes,
        )
        db.add(workspace)
        db.flush()
        return workspace

    workspace.primary_contact_name = booking.name
    workspace.primary_contact_email = booking.email
    workspace.primary_contact_phone = booking.phone
    workspace.source_booking_request_id = booking.id
    if portal_notes:
        workspace.portal_notes = portal_notes
    db.add(workspace)
    db.flush()
    return workspace


def _ensure_workspace_meeting(
    db: Session,
    *,
    workspace: ClientWorkspace,
    booking: BookingRequest,
) -> ClientWorkspaceMeeting:
    meeting = db.scalar(
        select(ClientWorkspaceMeeting).where(ClientWorkspaceMeeting.booking_request_id == booking.id)
    )

    if meeting is None:
        meeting = ClientWorkspaceMeeting(
            workspace_id=workspace.id,
            booking_request_id=booking.id,
            meeting_label=_build_meeting_label(booking),
            meet_url=booking.meet_url,
            meeting_notes=booking.meeting_notes,
            transcript_text=booking.transcript_text,
            transcript_summary=booking.transcript_summary,
            meeting_started_at=booking.meeting_started_at,
            meeting_ended_at=booking.meeting_ended_at,
            is_visible_to_client=True,
            synced_from_booking_at=_now_local(),
        )
        db.add(meeting)
        db.flush()
        return meeting

    meeting.workspace_id = workspace.id
    meeting.meeting_label = _build_meeting_label(booking)
    meeting.meet_url = booking.meet_url
    meeting.meeting_notes = booking.meeting_notes
    meeting.transcript_text = booking.transcript_text
    meeting.transcript_summary = booking.transcript_summary
    meeting.meeting_started_at = booking.meeting_started_at
    meeting.meeting_ended_at = booking.meeting_ended_at
    meeting.synced_from_booking_at = _now_local()
    db.add(meeting)
    db.flush()
    return meeting


def _create_workspace_invite(
    db: Session,
    *,
    workspace: ClientWorkspace,
    invite_email: str,
    invite_ttl_hours: int,
) -> tuple[ClientWorkspaceInvite, str]:
    raw_token = secrets.token_urlsafe(32)
    invite_token_hash = hashlib.sha256(raw_token.encode('utf-8')).hexdigest()
    now_local = _now_local()

    invite = ClientWorkspaceInvite(
        workspace_id=workspace.id,
        invite_email=invite_email,
        invite_token_hash=invite_token_hash,
        invite_status='pending',
        expires_at=now_local + timedelta(hours=invite_ttl_hours),
    )

    workspace.workspace_status = 'invited'
    db.add(invite)
    db.add(workspace)
    db.flush()

    return invite, raw_token


def _build_detail_response(
    *,
    db: Session,
    booking: BookingRequest,
    workspace: ClientWorkspace,
    setup_token: str | None = None,
) -> AdminClientWorkspaceDetailResponse:
    auto_sync_workspace_pending_google_artifacts_best_effort(db, workspace_id=workspace.id)
    meetings = _load_workspace_meetings(db, workspace.id)
    invites = _load_workspace_invites(db, workspace.id)
    account = _load_workspace_account(db, workspace.id)

    return AdminClientWorkspaceDetailResponse(
        workspace_id=workspace.id,
        workspace_status=workspace.workspace_status,
        source_booking_request_id=workspace.source_booking_request_id,
        source_booking_status=booking.status,
        source_meeting_status=booking.meeting_status,
        primary_contact_name=workspace.primary_contact_name,
        primary_contact_email=workspace.primary_contact_email,
        primary_contact_phone=workspace.primary_contact_phone,
        portal_notes=workspace.portal_notes,
        activated_at=workspace.activated_at.isoformat() if workspace.activated_at else None,
        created_at=workspace.created_at.isoformat(),
        account=_serialize_account(account),
        meetings=[_serialize_meeting(db, item) for item in meetings],
        invites=[_serialize_invite(item) for item in invites],
        drive=_serialize_drive_info(workspace),
        setup_token=setup_token,
        setup_path=(f'/cliente/ativacao/{setup_token}' if setup_token else None),
        setup_url=build_client_setup_url(f'/cliente/ativacao/{setup_token}') if setup_token else None,
    )


def _serialize_workspace_summary(db: Session, workspace: ClientWorkspace) -> AdminClientWorkspaceSummaryItem:
    auto_sync_workspace_pending_google_artifacts_best_effort(db, workspace_id=workspace.id)
    booking = db.get(BookingRequest, workspace.source_booking_request_id) if workspace.source_booking_request_id else None
    meetings = _load_workspace_meetings(db, workspace.id)
    invites = _load_workspace_invites(db, workspace.id)
    account = _load_workspace_account(db, workspace.id)
    serialized_meetings = [_serialize_meeting(db, item) for item in meetings]
    serialized_invites = [_serialize_invite(item) for item in invites]
    latest_meeting = serialized_meetings[0] if serialized_meetings else None
    latest_invite = serialized_invites[0] if serialized_invites else None
    has_client_access = bool(workspace.activated_at) or bool(account and account.last_login_at) or any(invite.accepted_at for invite in invites)

    return AdminClientWorkspaceSummaryItem(
        workspace_id=workspace.id,
        workspace_status=workspace.workspace_status,
        source_booking_request_id=workspace.source_booking_request_id,
        source_booking_status=booking.status if booking else 'unknown',
        source_meeting_status=booking.meeting_status if booking else 'unknown',
        primary_contact_name=workspace.primary_contact_name,
        primary_contact_email=workspace.primary_contact_email,
        primary_contact_phone=workspace.primary_contact_phone,
        portal_notes=workspace.portal_notes,
        activated_at=workspace.activated_at.isoformat() if workspace.activated_at else None,
        created_at=workspace.created_at.isoformat(),
        has_client_access=has_client_access,
        latest_invite_status=latest_invite.invite_status if latest_invite else None,
        latest_invite_sent_at=latest_invite.sent_at if latest_invite and latest_invite.sent_at else None,
        latest_invite_accepted_at=latest_invite.accepted_at if latest_invite and latest_invite.accepted_at else None,
        meetings_count=len(serialized_meetings),
        visible_meetings_count=sum(1 for meeting in serialized_meetings if meeting.is_visible_to_client),
        latest_meeting=latest_meeting,
        account=_serialize_account(account),
        invites=serialized_invites,
        meetings=serialized_meetings,
        drive=_serialize_drive_info(workspace),
    )


def list_client_workspaces(db: Session) -> AdminClientWorkspaceListResponse:
    workspaces = db.scalars(
        select(ClientWorkspace)
        .order_by(ClientWorkspace.created_at.desc(), ClientWorkspace.id.desc())
    ).all()

    return AdminClientWorkspaceListResponse(
        items=[_serialize_workspace_summary(db, workspace) for workspace in workspaces]
    )


def provision_client_workspace_for_booking(
    db: Session,
    *,
    booking_id: int,
    payload: AdminClientWorkspaceProvisionRequest,
) -> AdminClientWorkspaceDetailResponse:
    booking = _get_booking_or_404(db, booking_id)

    workspace = _ensure_workspace(
        db,
        booking=booking,
        portal_notes=payload.portal_notes,
    )
    _ensure_workspace_meeting(db, workspace=workspace, booking=booking)
    _ensure_workspace_drive_structure(
        db=db,
        workspace=workspace,
        raise_on_failure=False,
    )

    setup_token: str | None = None
    if payload.create_invite:
        _, setup_token = _create_workspace_invite(
            db,
            workspace=workspace,
            invite_email=booking.email,
            invite_ttl_hours=payload.invite_ttl_hours,
        )

    db.commit()

    booking = _get_booking_or_404(db, booking_id)
    workspace = db.get(ClientWorkspace, workspace.id)
    if workspace is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail='Workspace do cliente não pôde ser recarregado após a provisão.',
        )

    return _build_detail_response(
        db=db,
        booking=booking,
        workspace=workspace,
        setup_token=setup_token,
    )


def get_client_workspace_by_booking(
    db: Session,
    *,
    booking_id: int,
) -> AdminClientWorkspaceDetailResponse:
    booking = _get_booking_or_404(db, booking_id)
    meeting = db.scalar(
        select(ClientWorkspaceMeeting).where(
            ClientWorkspaceMeeting.booking_request_id == booking.id
        )
    )

    if meeting is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail='Ainda não existe workspace provisionado para esta solicitação.',
        )

    workspace = db.get(ClientWorkspace, meeting.workspace_id)
    if workspace is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail='Workspace do cliente não encontrado.',
        )

    return _build_detail_response(
        db=db,
        booking=booking,
        workspace=workspace,
    )


def regenerate_client_workspace_invite(
    db: Session,
    *,
    workspace_id: int,
    payload: AdminClientWorkspaceInviteRefreshRequest,
) -> AdminClientWorkspaceDetailResponse:
    workspace = db.get(ClientWorkspace, workspace_id)
    if workspace is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail='Workspace do cliente não encontrado.',
        )

    booking_id = workspace.source_booking_request_id
    if booking_id is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail='Este workspace não possui solicitação de origem para gerar um novo acesso.',
        )

    booking = _get_booking_or_404(db, booking_id)
    _, setup_token = _create_workspace_invite(
        db,
        workspace=workspace,
        invite_email=workspace.primary_contact_email or booking.email,
        invite_ttl_hours=payload.invite_ttl_hours,
    )
    db.commit()

    booking = _get_booking_or_404(db, booking_id)
    workspace = db.get(ClientWorkspace, workspace_id)
    if workspace is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail='Workspace do cliente não pôde ser recarregado após gerar novo acesso.',
        )

    return _build_detail_response(
        db=db,
        booking=booking,
        workspace=workspace,
        setup_token=setup_token,
    )


def sync_client_workspace_drive_folders(
    db: Session,
    *,
    workspace_id: int,
) -> AdminClientWorkspaceDetailResponse:
    workspace = db.get(ClientWorkspace, workspace_id)
    if workspace is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail='Workspace do cliente não encontrado.',
        )

    booking_id = workspace.source_booking_request_id
    if booking_id is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail='Este workspace não possui solicitação de origem para sincronizar a estrutura do Drive.',
        )

    booking = _get_booking_or_404(db, booking_id)
    _ensure_workspace_drive_structure(
        db=db,
        workspace=workspace,
        raise_on_failure=True,
    )
    db.commit()

    booking = _get_booking_or_404(db, booking_id)
    workspace = db.get(ClientWorkspace, workspace_id)
    if workspace is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail='Workspace do cliente não pôde ser recarregado após sincronizar o Drive.',
        )

    return _build_detail_response(
        db=db,
        booking=booking,
        workspace=workspace,
    )
