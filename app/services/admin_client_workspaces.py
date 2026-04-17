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
from app.models.client_workspace_invite import ClientWorkspaceInvite
from app.models.client_workspace_meeting import ClientWorkspaceMeeting
from app.schemas.admin_client_workspaces import (
    AdminClientWorkspaceDetailResponse,
    AdminClientWorkspaceInviteItem,
    AdminClientWorkspaceMeetingItem,
    AdminClientWorkspaceProvisionRequest,
)


def _now_local() -> datetime:
    return datetime.now(ZoneInfo(settings.app_timezone))


def _get_booking_or_404(db: Session, booking_id: int) -> BookingRequest:
    booking = db.get(BookingRequest, booking_id)
    if booking is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Solicitação de reunião não encontrada.",
        )
    return booking


def _build_meeting_label(booking: BookingRequest) -> str:
    start_text = booking.start_time.strftime("%H:%M") if booking.start_time else None
    end_text = booking.end_time.strftime("%H:%M") if booking.end_time else None

    if booking.booking_date and start_text and end_text:
        return f"{booking.booking_date.strftime('%d/%m/%Y')} • {start_text} às {end_text}"

    if booking.booking_date:
        return booking.booking_date.strftime("%d/%m/%Y")

    return f"Solicitação #{booking.id}"


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


def _serialize_meeting(meeting: ClientWorkspaceMeeting) -> AdminClientWorkspaceMeetingItem:
    return AdminClientWorkspaceMeetingItem(
        id=meeting.id,
        booking_request_id=meeting.booking_request_id,
        meeting_label=meeting.meeting_label,
        meet_url=meeting.meet_url,
        recording_url=meeting.recording_url,
        recording_provider=meeting.recording_provider,
        has_transcript=bool(meeting.transcript_text or meeting.transcript_summary),
        transcript_summary=meeting.transcript_summary,
        meeting_notes=meeting.meeting_notes,
        is_visible_to_client=meeting.is_visible_to_client,
        synced_from_booking_at=(
            meeting.synced_from_booking_at.isoformat()
            if meeting.synced_from_booking_at
            else None
        ),
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


def _ensure_workspace(db: Session, booking: BookingRequest, portal_notes: str | None) -> ClientWorkspace:
    workspace = _find_workspace_for_contact(db, booking)

    if workspace is None:
        workspace = ClientWorkspace(
            source_booking_request_id=booking.id,
            primary_contact_name=booking.name,
            primary_contact_email=booking.email,
            primary_contact_phone=booking.phone,
            workspace_status="provisioned",
            portal_notes=portal_notes,
        )
        db.add(workspace)
        db.flush()
        return workspace

    workspace.primary_contact_name = booking.name
    workspace.primary_contact_email = booking.email
    workspace.primary_contact_phone = booking.phone

    if portal_notes is not None:
        workspace.portal_notes = portal_notes

    if workspace.source_booking_request_id is None:
        workspace.source_booking_request_id = booking.id

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
        select(ClientWorkspaceMeeting).where(
            ClientWorkspaceMeeting.booking_request_id == booking.id
        )
    )

    if meeting is None:
        meeting = ClientWorkspaceMeeting(
            workspace_id=workspace.id,
            booking_request_id=booking.id,
            meeting_label=_build_meeting_label(booking),
            is_visible_to_client=True,
        )

    meeting.workspace_id = workspace.id
    meeting.meeting_label = _build_meeting_label(booking)
    meeting.meet_url = booking.meet_url
    meeting.transcript_text = booking.transcript_text
    meeting.transcript_summary = booking.transcript_summary
    meeting.meeting_notes = booking.meeting_notes
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
    invite_token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    now_local = _now_local()

    invite = ClientWorkspaceInvite(
        workspace_id=workspace.id,
        invite_email=invite_email,
        invite_token_hash=invite_token_hash,
        invite_status="pending",
        expires_at=now_local + timedelta(hours=invite_ttl_hours),
    )

    workspace.workspace_status = "invited"
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
    meetings = _load_workspace_meetings(db, workspace.id)
    invites = _load_workspace_invites(db, workspace.id)

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
        meetings=[_serialize_meeting(item) for item in meetings],
        invites=[_serialize_invite(item) for item in invites],
        setup_token=setup_token,
        setup_path=(f"/cliente/ativacao/{setup_token}" if setup_token else None),
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
            detail="Workspace do cliente não pôde ser recarregado após a provisão.",
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
            detail="Ainda não existe workspace provisionado para esta solicitação.",
        )

    workspace = db.get(ClientWorkspace, meeting.workspace_id)
    if workspace is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace do cliente não encontrado.",
        )

    return _build_detail_response(
        db=db,
        booking=booking,
        workspace=workspace,
    )