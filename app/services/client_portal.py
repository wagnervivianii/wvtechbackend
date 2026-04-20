from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.client_workspace_meeting import ClientWorkspaceMeeting
from app.schemas.client_portal import (
    ClientPortalMeetingArtifactItem,
    ClientPortalMeetingItem,
    ClientPortalWorkspaceResponse,
)
from app.services.client_auth import get_authenticated_client_context
from app.services.client_workspace_artifacts import (
    auto_sync_workspace_pending_google_artifacts_best_effort,
    serialize_client_artifacts_for_meeting,
)


def get_client_workspace_portal(db: Session, claims: dict[str, object]) -> ClientPortalWorkspaceResponse:
    context = get_authenticated_client_context(db, claims)
    workspace = context.workspace
    auto_sync_workspace_pending_google_artifacts_best_effort(db, workspace_id=workspace.id)
    meetings = db.scalars(
        select(ClientWorkspaceMeeting)
        .where(ClientWorkspaceMeeting.workspace_id == workspace.id)
        .where(ClientWorkspaceMeeting.is_visible_to_client.is_(True))
        .order_by(ClientWorkspaceMeeting.created_at.desc(), ClientWorkspaceMeeting.id.desc())
    ).all()

    return ClientPortalWorkspaceResponse(
        workspace_id=workspace.id,
        workspace_status=workspace.workspace_status,
        primary_contact_name=workspace.primary_contact_name,
        primary_contact_email=workspace.primary_contact_email,
        primary_contact_phone=workspace.primary_contact_phone,
        portal_notes=workspace.portal_notes,
        activated_at=workspace.activated_at.isoformat() if workspace.activated_at else None,
        created_at=workspace.created_at.isoformat(),
        meetings=[
            ClientPortalMeetingItem(
                id=meeting.id,
                booking_request_id=meeting.booking_request_id,
                meeting_label=meeting.meeting_label,
                meet_url=meeting.meet_url,
                recording_url=meeting.recording_url,
                recording_provider=meeting.recording_provider,
                transcript_summary=meeting.transcript_summary,
                transcript_text=meeting.transcript_text,
                meeting_notes=meeting.meeting_notes,
                meeting_started_at=(meeting.meeting_started_at.isoformat() if meeting.meeting_started_at else None),
                meeting_ended_at=(meeting.meeting_ended_at.isoformat() if meeting.meeting_ended_at else None),
                synced_from_booking_at=(meeting.synced_from_booking_at.isoformat() if meeting.synced_from_booking_at else None),
                artifacts=serialize_client_artifacts_for_meeting(db, meeting.id),
            )
            for meeting in meetings
        ],
    )
