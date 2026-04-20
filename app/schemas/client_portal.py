from __future__ import annotations

from pydantic import BaseModel, EmailStr


class ClientPortalMeetingArtifactItem(BaseModel):
    id: int
    artifact_type: str
    artifact_status: str
    artifact_label: str | None
    source_provider: str | None
    drive_file_name: str | None
    drive_web_view_link: str | None
    mime_type: str | None
    file_size_bytes: int | None
    text_content: str | None
    summary_text: str | None
    captured_at: str | None


class ClientPortalMeetingItem(BaseModel):
    id: int
    booking_request_id: int
    meeting_label: str
    meet_url: str | None
    recording_url: str | None
    recording_provider: str | None
    transcript_summary: str | None
    transcript_text: str | None
    meeting_notes: str | None
    meeting_started_at: str | None
    meeting_ended_at: str | None
    synced_from_booking_at: str | None
    artifacts: list[ClientPortalMeetingArtifactItem]


class ClientPortalWorkspaceResponse(BaseModel):
    workspace_id: int
    workspace_status: str
    primary_contact_name: str
    primary_contact_email: EmailStr
    primary_contact_phone: str
    portal_notes: str | None
    activated_at: str | None
    created_at: str
    meetings: list[ClientPortalMeetingItem]
