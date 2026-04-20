from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.client_workspace import ClientWorkspace
from app.models.client_workspace_meeting import ClientWorkspaceMeeting
from app.models.client_workspace_meeting_artifact import ClientWorkspaceMeetingArtifact
from app.schemas.admin_client_workspaces import (
    AdminClientWorkspaceArtifactUpsertRequest,
    AdminClientWorkspaceArtifactsResponse,
    AdminClientWorkspaceMeetingArtifactItem,
    AdminClientWorkspaceMeetingItem,
)
from app.schemas.client_portal import ClientPortalMeetingArtifactItem

ALLOWED_ARTIFACT_TYPES = {'recording', 'transcript', 'summary', 'notes'}
ALLOWED_ARTIFACT_STATUSES = {'pending', 'available', 'failed', 'archived'}


def _now_local() -> datetime:
    return datetime.now(ZoneInfo(settings.app_timezone))


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _validate_artifact_type(value: str) -> str:
    normalized = value.strip().lower()
    if normalized not in ALLOWED_ARTIFACT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail='artifact_type inválido. Use recording, transcript, summary ou notes.',
        )
    return normalized


def _validate_artifact_status(value: str) -> str:
    normalized = value.strip().lower()
    if normalized not in ALLOWED_ARTIFACT_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail='artifact_status inválido. Use pending, available, failed ou archived.',
        )
    return normalized


def _build_default_artifact_label(artifact_type: str, meeting: ClientWorkspaceMeeting) -> str:
    names = {
        'recording': 'Gravação',
        'transcript': 'Transcrição',
        'summary': 'Resumo',
        'notes': 'Notas',
    }
    return f"{names.get(artifact_type, 'Artefato')} • {meeting.meeting_label}"


def _load_artifact_models_for_meeting(
    db: Session,
    *,
    meeting_id: int,
    include_hidden: bool,
) -> list[ClientWorkspaceMeetingArtifact]:
    query = (
        select(ClientWorkspaceMeetingArtifact)
        .where(ClientWorkspaceMeetingArtifact.meeting_id == meeting_id)
        .order_by(
            ClientWorkspaceMeetingArtifact.captured_at.desc(),
            ClientWorkspaceMeetingArtifact.created_at.desc(),
            ClientWorkspaceMeetingArtifact.id.desc(),
        )
    )

    if not include_hidden:
        query = query.where(ClientWorkspaceMeetingArtifact.is_visible_to_client.is_(True))

    return db.scalars(query).all()


def _serialize_admin_artifact(artifact: ClientWorkspaceMeetingArtifact) -> AdminClientWorkspaceMeetingArtifactItem:
    return AdminClientWorkspaceMeetingArtifactItem(
        id=artifact.id,
        artifact_type=artifact.artifact_type,
        artifact_status=artifact.artifact_status,
        artifact_label=artifact.artifact_label,
        source_provider=artifact.source_provider,
        google_conference_record_name=artifact.google_conference_record_name,
        google_artifact_resource_name=artifact.google_artifact_resource_name,
        source_download_url=artifact.source_download_url,
        drive_file_id=artifact.drive_file_id,
        drive_file_name=artifact.drive_file_name,
        drive_web_view_link=artifact.drive_web_view_link,
        mime_type=artifact.mime_type,
        file_size_bytes=artifact.file_size_bytes,
        text_content=artifact.text_content,
        summary_text=artifact.summary_text,
        metadata_json=artifact.metadata_json,
        captured_at=_iso(artifact.captured_at),
        last_synced_at=_iso(artifact.last_synced_at),
        is_visible_to_client=artifact.is_visible_to_client,
        created_at=artifact.created_at.isoformat(),
        updated_at=artifact.updated_at.isoformat(),
    )


def _serialize_client_artifact(artifact: ClientWorkspaceMeetingArtifact) -> ClientPortalMeetingArtifactItem:
    return ClientPortalMeetingArtifactItem(
        id=artifact.id,
        artifact_type=artifact.artifact_type,
        artifact_status=artifact.artifact_status,
        artifact_label=artifact.artifact_label,
        source_provider=artifact.source_provider,
        drive_file_name=artifact.drive_file_name,
        drive_web_view_link=artifact.drive_web_view_link,
        mime_type=artifact.mime_type,
        file_size_bytes=artifact.file_size_bytes,
        text_content=artifact.text_content,
        summary_text=artifact.summary_text,
        captured_at=_iso(artifact.captured_at),
    )


def serialize_admin_artifacts_for_meeting(db: Session, meeting_id: int) -> list[AdminClientWorkspaceMeetingArtifactItem]:
    artifacts = _load_artifact_models_for_meeting(db, meeting_id=meeting_id, include_hidden=True)
    return [_serialize_admin_artifact(artifact) for artifact in artifacts]


def serialize_client_artifacts_for_meeting(db: Session, meeting_id: int) -> list[ClientPortalMeetingArtifactItem]:
    artifacts = _load_artifact_models_for_meeting(db, meeting_id=meeting_id, include_hidden=False)
    return [_serialize_client_artifact(artifact) for artifact in artifacts]


def attach_admin_artifacts_to_meeting_item(
    db: Session,
    meeting_item: AdminClientWorkspaceMeetingItem,
) -> AdminClientWorkspaceMeetingItem:
    meeting_item.artifacts = serialize_admin_artifacts_for_meeting(db, meeting_item.id)
    return meeting_item


def _pick_latest_available_artifact(
    artifacts: list[ClientWorkspaceMeetingArtifact],
    artifact_type: str,
) -> ClientWorkspaceMeetingArtifact | None:
    for artifact in artifacts:
        if artifact.artifact_type == artifact_type and artifact.artifact_status == 'available':
            return artifact
    return None


def sync_meeting_legacy_fields_from_artifacts(
    db: Session,
    *,
    meeting: ClientWorkspaceMeeting,
) -> None:
    artifacts = _load_artifact_models_for_meeting(db, meeting_id=meeting.id, include_hidden=True)

    recording = _pick_latest_available_artifact(artifacts, 'recording')
    transcript = _pick_latest_available_artifact(artifacts, 'transcript')
    summary = _pick_latest_available_artifact(artifacts, 'summary')
    notes = _pick_latest_available_artifact(artifacts, 'notes')

    if recording is not None:
        meeting.recording_url = (
            recording.drive_web_view_link
            or recording.source_download_url
            or meeting.recording_url
        )
        meeting.recording_provider = recording.source_provider or meeting.recording_provider
        meeting.recording_file_id = recording.drive_file_id or recording.google_artifact_resource_name

    if transcript is not None and transcript.text_content:
        meeting.transcript_text = transcript.text_content

    if summary is not None:
        meeting.transcript_summary = summary.summary_text or summary.text_content or meeting.transcript_summary
    elif transcript is not None and transcript.summary_text:
        meeting.transcript_summary = transcript.summary_text

    if notes is not None:
        meeting.meeting_notes = notes.text_content or notes.summary_text or meeting.meeting_notes

    db.add(meeting)
    db.flush()


def _find_existing_artifact(
    db: Session,
    *,
    meeting_id: int,
    artifact_type: str,
    payload: AdminClientWorkspaceArtifactUpsertRequest,
) -> ClientWorkspaceMeetingArtifact | None:
    if payload.google_artifact_resource_name:
        return db.scalar(
            select(ClientWorkspaceMeetingArtifact)
            .where(ClientWorkspaceMeetingArtifact.meeting_id == meeting_id)
            .where(ClientWorkspaceMeetingArtifact.google_artifact_resource_name == payload.google_artifact_resource_name)
        )

    if payload.drive_file_id:
        return db.scalar(
            select(ClientWorkspaceMeetingArtifact)
            .where(ClientWorkspaceMeetingArtifact.meeting_id == meeting_id)
            .where(ClientWorkspaceMeetingArtifact.drive_file_id == payload.drive_file_id)
        )

    return db.scalar(
        select(ClientWorkspaceMeetingArtifact)
        .where(ClientWorkspaceMeetingArtifact.meeting_id == meeting_id)
        .where(ClientWorkspaceMeetingArtifact.artifact_type == artifact_type)
        .order_by(ClientWorkspaceMeetingArtifact.updated_at.desc(), ClientWorkspaceMeetingArtifact.id.desc())
    )


def upsert_workspace_meeting_artifact(
    db: Session,
    *,
    workspace_id: int,
    meeting_id: int,
    payload: AdminClientWorkspaceArtifactUpsertRequest,
) -> AdminClientWorkspaceMeetingArtifactItem:
    workspace = db.get(ClientWorkspace, workspace_id)
    if workspace is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail='Workspace do cliente não encontrado.',
        )

    meeting = db.get(ClientWorkspaceMeeting, meeting_id)
    if meeting is None or meeting.workspace_id != workspace_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail='Reunião do workspace não encontrada.',
        )

    artifact_type = _validate_artifact_type(payload.artifact_type)
    artifact_status = _validate_artifact_status(payload.artifact_status)

    artifact = _find_existing_artifact(
        db,
        meeting_id=meeting.id,
        artifact_type=artifact_type,
        payload=payload,
    )

    if artifact is None:
        artifact = ClientWorkspaceMeetingArtifact(
            workspace_id=workspace.id,
            meeting_id=meeting.id,
            artifact_type=artifact_type,
        )

    artifact.artifact_type = artifact_type
    artifact.artifact_status = artifact_status
    artifact.artifact_label = payload.artifact_label or artifact.artifact_label or _build_default_artifact_label(artifact_type, meeting)
    artifact.source_provider = payload.source_provider or artifact.source_provider
    artifact.google_conference_record_name = payload.google_conference_record_name or artifact.google_conference_record_name
    artifact.google_artifact_resource_name = payload.google_artifact_resource_name or artifact.google_artifact_resource_name
    artifact.source_download_url = payload.source_download_url or artifact.source_download_url
    artifact.drive_file_id = payload.drive_file_id or artifact.drive_file_id
    artifact.drive_file_name = payload.drive_file_name or artifact.drive_file_name
    artifact.drive_web_view_link = payload.drive_web_view_link or artifact.drive_web_view_link
    artifact.mime_type = payload.mime_type or artifact.mime_type
    artifact.file_size_bytes = payload.file_size_bytes if payload.file_size_bytes is not None else artifact.file_size_bytes
    artifact.text_content = payload.text_content if payload.text_content is not None else artifact.text_content
    artifact.summary_text = payload.summary_text if payload.summary_text is not None else artifact.summary_text
    artifact.metadata_json = payload.metadata_json if payload.metadata_json is not None else artifact.metadata_json
    artifact.captured_at = payload.captured_at or artifact.captured_at or _now_local()
    artifact.last_synced_at = _now_local()
    artifact.is_visible_to_client = payload.is_visible_to_client

    db.add(artifact)
    db.flush()

    sync_meeting_legacy_fields_from_artifacts(db, meeting=meeting)
    db.commit()
    db.refresh(artifact)

    return _serialize_admin_artifact(artifact)


def get_workspace_artifacts_for_admin(
    db: Session,
    *,
    workspace_id: int,
    meetings: list[AdminClientWorkspaceMeetingItem],
) -> AdminClientWorkspaceArtifactsResponse:
    workspace = db.get(ClientWorkspace, workspace_id)
    if workspace is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail='Workspace do cliente não encontrado.',
        )

    hydrated_meetings = [attach_admin_artifacts_to_meeting_item(db, meeting_item) for meeting_item in meetings]

    return AdminClientWorkspaceArtifactsResponse(
        workspace_id=workspace.id,
        primary_contact_name=workspace.primary_contact_name,
        primary_contact_email=workspace.primary_contact_email,
        meetings=hydrated_meetings,
    )
