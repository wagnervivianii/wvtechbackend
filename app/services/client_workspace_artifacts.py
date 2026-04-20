from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.booking_request import BookingRequest
from app.models.client_workspace import ClientWorkspace
from app.models.client_workspace_meeting import ClientWorkspaceMeeting
from app.models.client_workspace_meeting_artifact import ClientWorkspaceMeetingArtifact
from app.schemas.admin_client_workspaces import (
    AdminClientWorkspaceArtifactUpsertRequest,
    AdminClientWorkspaceArtifactsResponse,
    AdminClientWorkspaceMeetingArtifactBatchSyncItem,
    AdminClientWorkspaceMeetingArtifactBatchSyncRequest,
    AdminClientWorkspaceMeetingArtifactBatchSyncResponse,
    AdminClientWorkspaceMeetingArtifactItem,
    AdminClientWorkspaceMeetingArtifactSyncResponse,
    AdminClientWorkspaceMeetingItem,
)
from app.schemas.client_portal import ClientPortalMeetingArtifactItem
from app.services.google_drive import (
    GoogleDriveIntegrationError,
    GoogleDriveIntegrationNotConfiguredError,
    get_google_drive_file_metadata,
    move_google_drive_file_to_folder,
)
from app.services.google_meet_artifacts import (
    GoogleMeetArtifactsIntegrationError,
    GoogleMeetArtifactsNotConfiguredError,
    build_transcript_text,
    extract_meeting_code_from_meet_url,
    find_best_conference_record_for_booking,
    list_recordings_for_conference_record,
    list_smart_notes_for_conference_record,
    list_transcript_entries,
    list_transcripts_for_conference_record,
)

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


def _load_workspace_and_meeting_or_404(
    db: Session,
    *,
    workspace_id: int,
    meeting_id: int,
) -> tuple[ClientWorkspace, ClientWorkspaceMeeting]:
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

    return workspace, meeting


def _persist_artifact_from_payload(
    db: Session,
    *,
    workspace: ClientWorkspace,
    meeting: ClientWorkspaceMeeting,
    payload: AdminClientWorkspaceArtifactUpsertRequest,
) -> ClientWorkspaceMeetingArtifact:
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
    return artifact


def upsert_workspace_meeting_artifact(
    db: Session,
    *,
    workspace_id: int,
    meeting_id: int,
    payload: AdminClientWorkspaceArtifactUpsertRequest,
) -> AdminClientWorkspaceMeetingArtifactItem:
    workspace, meeting = _load_workspace_and_meeting_or_404(
        db,
        workspace_id=workspace_id,
        meeting_id=meeting_id,
    )

    artifact = _persist_artifact_from_payload(
        db,
        workspace=workspace,
        meeting=meeting,
        payload=payload,
    )
    db.commit()
    db.refresh(artifact)

    return _serialize_admin_artifact(artifact)


def _ensure_workspace_ready_for_drive_artifacts(workspace: ClientWorkspace) -> None:
    if not workspace.drive_meet_artifacts_folder_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail='A pasta 01_meet_artifacts ainda não está pronta no Google Drive deste workspace.',
        )


def _booking_effective_end_at(booking: BookingRequest) -> datetime | None:
    if booking.booking_date is None:
        return None

    tz = ZoneInfo(settings.app_timezone)
    if booking.end_time is not None:
        return datetime.combine(booking.booking_date, booking.end_time, tzinfo=tz)
    if booking.start_time is not None:
        return datetime.combine(booking.booking_date, booking.start_time, tzinfo=tz)
    return None


def _meeting_is_past_due_for_google_sync(booking: BookingRequest, meeting: ClientWorkspaceMeeting) -> bool:
    now_local = _now_local()
    if meeting.meeting_ended_at is not None:
        return meeting.meeting_ended_at <= now_local

    booking_end_at = _booking_effective_end_at(booking)
    if booking_end_at is None:
        return False

    return booking_end_at <= now_local


def _meeting_already_has_google_artifacts(db: Session, meeting_id: int) -> bool:
    artifacts = _load_artifact_models_for_meeting(db, meeting_id=meeting_id, include_hidden=True)
    return any(
        artifact.source_provider == 'google_meet'
        and artifact.artifact_status == 'available'
        and (artifact.google_artifact_resource_name or artifact.google_conference_record_name)
        for artifact in artifacts
    )


def _list_workspace_meetings_eligible_for_google_sync(
    db: Session,
    *,
    workspace_id: int,
    force_resync: bool,
    max_meetings: int,
) -> list[tuple[ClientWorkspaceMeeting, BookingRequest]]:
    meetings = db.scalars(
        select(ClientWorkspaceMeeting)
        .where(ClientWorkspaceMeeting.workspace_id == workspace_id)
        .order_by(ClientWorkspaceMeeting.meeting_ended_at.asc().nullsfirst(), ClientWorkspaceMeeting.id.asc())
    ).all()

    eligible: list[tuple[ClientWorkspaceMeeting, BookingRequest]] = []
    for meeting in meetings:
        booking = db.get(BookingRequest, meeting.booking_request_id)
        if booking is None:
            continue

        effective_meet_url = meeting.meet_url or booking.meet_url
        if not effective_meet_url:
            continue

        if not _meeting_is_past_due_for_google_sync(booking, meeting):
            continue

        if not force_resync and _meeting_already_has_google_artifacts(db, meeting.id):
            continue

        eligible.append((meeting, booking))
        if len(eligible) >= max_meetings:
            break

    return eligible


def _get_booking_for_meeting_or_404(db: Session, meeting: ClientWorkspaceMeeting) -> BookingRequest:
    booking = db.get(BookingRequest, meeting.booking_request_id)
    if booking is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail='Booking de origem da reunião não encontrado.',
        )
    return booking


def _build_transcript_metadata(entries) -> dict:
    languages = sorted({entry.language_code for entry in entries if entry.language_code})
    return {
        'entry_count': len(entries),
        'language_codes': languages,
        'sync_origin': 'google_meet_transcript_entries',
    }


def _sync_recordings_from_google(
    db: Session,
    *,
    workspace: ClientWorkspace,
    meeting: ClientWorkspaceMeeting,
    conference_record_name: str,
) -> int:
    recordings = list_recordings_for_conference_record(conference_record_name)
    synced = 0

    for recording in recordings:
        if recording.state != 'FILE_GENERATED' or not recording.drive_file_id:
            continue

        moved_file = move_google_drive_file_to_folder(
            file_id=recording.drive_file_id,
            target_folder_id=workspace.drive_meet_artifacts_folder_id,
        )

        payload = AdminClientWorkspaceArtifactUpsertRequest(
            artifact_type='recording',
            artifact_status='available',
            artifact_label=None,
            source_provider='google_meet',
            google_conference_record_name=conference_record_name,
            google_artifact_resource_name=recording.name,
            source_download_url=recording.export_uri,
            drive_file_id=moved_file.file_id,
            drive_file_name=moved_file.file_name,
            drive_web_view_link=moved_file.web_view_link,
            mime_type=moved_file.mime_type,
            file_size_bytes=moved_file.file_size_bytes,
            text_content=None,
            summary_text=None,
            metadata_json=None,
            captured_at=recording.end_time or recording.start_time,
            is_visible_to_client=True,
        )
        _persist_artifact_from_payload(db, workspace=workspace, meeting=meeting, payload=payload)
        synced += 1

    return synced


def _sync_transcripts_from_google(
    db: Session,
    *,
    workspace: ClientWorkspace,
    meeting: ClientWorkspaceMeeting,
    conference_record_name: str,
) -> int:
    transcripts = list_transcripts_for_conference_record(conference_record_name)
    synced = 0

    for transcript in transcripts:
        if transcript.state != 'FILE_GENERATED' or not transcript.document_id:
            continue

        moved_file = move_google_drive_file_to_folder(
            file_id=transcript.document_id,
            target_folder_id=workspace.drive_meet_artifacts_folder_id,
        )
        entries = list_transcript_entries(transcript.name)
        transcript_text = build_transcript_text(entries)

        payload = AdminClientWorkspaceArtifactUpsertRequest(
            artifact_type='transcript',
            artifact_status='available',
            artifact_label=None,
            source_provider='google_meet',
            google_conference_record_name=conference_record_name,
            google_artifact_resource_name=transcript.name,
            source_download_url=transcript.export_uri,
            drive_file_id=moved_file.file_id,
            drive_file_name=moved_file.file_name,
            drive_web_view_link=moved_file.web_view_link,
            mime_type=moved_file.mime_type,
            file_size_bytes=moved_file.file_size_bytes,
            text_content=transcript_text,
            summary_text=None,
            metadata_json=_build_transcript_metadata(entries),
            captured_at=transcript.end_time or transcript.start_time,
            is_visible_to_client=True,
        )
        _persist_artifact_from_payload(db, workspace=workspace, meeting=meeting, payload=payload)
        synced += 1

    return synced


def _sync_smart_notes_from_google(
    db: Session,
    *,
    workspace: ClientWorkspace,
    meeting: ClientWorkspaceMeeting,
    conference_record_name: str,
) -> int:
    notes = list_smart_notes_for_conference_record(conference_record_name)
    synced = 0

    for note in notes:
        if note.state != 'FILE_GENERATED' or not note.document_id:
            continue

        moved_file = move_google_drive_file_to_folder(
            file_id=note.document_id,
            target_folder_id=workspace.drive_meet_artifacts_folder_id,
        )
        payload = AdminClientWorkspaceArtifactUpsertRequest(
            artifact_type='notes',
            artifact_status='available',
            artifact_label=None,
            source_provider='google_meet',
            google_conference_record_name=conference_record_name,
            google_artifact_resource_name=note.name,
            source_download_url=note.export_uri,
            drive_file_id=moved_file.file_id,
            drive_file_name=moved_file.file_name,
            drive_web_view_link=moved_file.web_view_link,
            mime_type=moved_file.mime_type,
            file_size_bytes=moved_file.file_size_bytes,
            text_content=None,
            summary_text=None,
            metadata_json={'sync_origin': 'google_meet_smart_notes'},
            captured_at=note.end_time or note.start_time,
            is_visible_to_client=True,
        )
        _persist_artifact_from_payload(db, workspace=workspace, meeting=meeting, payload=payload)
        synced += 1

    return synced


def sync_workspace_meeting_artifacts_from_google(
    db: Session,
    *,
    workspace_id: int,
    meeting_id: int,
) -> AdminClientWorkspaceMeetingArtifactSyncResponse:
    workspace, meeting = _load_workspace_and_meeting_or_404(
        db,
        workspace_id=workspace_id,
        meeting_id=meeting_id,
    )
    _ensure_workspace_ready_for_drive_artifacts(workspace)
    booking = _get_booking_for_meeting_or_404(db, meeting)
    meeting_code = extract_meeting_code_from_meet_url(meeting.meet_url or booking.meet_url)

    try:
        conference_record = find_best_conference_record_for_booking(booking)
    except GoogleMeetArtifactsNotConfiguredError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except GoogleMeetArtifactsIntegrationError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f'Falha ao consultar artefatos reais do Google Meet. {exc}',
        ) from exc

    if conference_record is None:
        return AdminClientWorkspaceMeetingArtifactSyncResponse(
            workspace_id=workspace.id,
            meeting_id=meeting.id,
            meeting_label=meeting.meeting_label,
            meeting_code=meeting_code,
            conference_record_name=None,
            sync_status='conference_not_found',
            message='Nenhuma conference record do Google Meet foi encontrada para esta reunião ainda.',
            synchronized_at=_iso(_now_local()),
            artifacts_found=0,
            artifacts_upserted=0,
            recordings_synced=0,
            transcripts_synced=0,
            notes_synced=0,
            artifacts=serialize_admin_artifacts_for_meeting(db, meeting.id),
        )

    if conference_record.start_time:
        meeting.meeting_started_at = conference_record.start_time
    if conference_record.end_time:
        meeting.meeting_ended_at = conference_record.end_time
    db.add(meeting)
    db.flush()

    try:
        recordings_synced = _sync_recordings_from_google(
            db,
            workspace=workspace,
            meeting=meeting,
            conference_record_name=conference_record.name,
        )
        transcripts_synced = _sync_transcripts_from_google(
            db,
            workspace=workspace,
            meeting=meeting,
            conference_record_name=conference_record.name,
        )
        notes_synced = _sync_smart_notes_from_google(
            db,
            workspace=workspace,
            meeting=meeting,
            conference_record_name=conference_record.name,
        )
    except GoogleDriveIntegrationNotConfiguredError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except (GoogleDriveIntegrationError, GoogleMeetArtifactsIntegrationError) as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f'Falha ao sincronizar artefatos do Google Meet com o Google Drive. {exc}',
        ) from exc

    db.commit()
    db.refresh(meeting)
    artifacts = serialize_admin_artifacts_for_meeting(db, meeting.id)
    artifacts_upserted = recordings_synced + transcripts_synced + notes_synced

    return AdminClientWorkspaceMeetingArtifactSyncResponse(
        workspace_id=workspace.id,
        meeting_id=meeting.id,
        meeting_label=meeting.meeting_label,
        meeting_code=meeting_code,
        conference_record_name=conference_record.name,
        sync_status='synchronized' if artifacts_upserted else 'no_artifacts_available',
        message=(
            'Artefatos reais do Google Meet sincronizados com sucesso.'
            if artifacts_upserted
            else 'A conference record foi encontrada, mas ainda não existem arquivos gerados prontos para ingestão.'
        ),
        synchronized_at=_iso(_now_local()),
        artifacts_found=artifacts_upserted,
        artifacts_upserted=artifacts_upserted,
        recordings_synced=recordings_synced,
        transcripts_synced=transcripts_synced,
        notes_synced=notes_synced,
        artifacts=artifacts,
    )



def sync_workspace_pending_google_artifacts(
    db: Session,
    *,
    workspace_id: int,
    payload: AdminClientWorkspaceMeetingArtifactBatchSyncRequest,
) -> AdminClientWorkspaceMeetingArtifactBatchSyncResponse:
    workspace = db.get(ClientWorkspace, workspace_id)
    if workspace is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail='Workspace do cliente não encontrado.',
        )

    _ensure_workspace_ready_for_drive_artifacts(workspace)

    eligible_meetings = _list_workspace_meetings_eligible_for_google_sync(
        db,
        workspace_id=workspace_id,
        force_resync=payload.force_resync,
        max_meetings=payload.max_meetings,
    )

    items: list[AdminClientWorkspaceMeetingArtifactBatchSyncItem] = []
    synchronized_count = 0
    no_artifacts_count = 0
    conference_not_found_count = 0
    failed_count = 0

    for meeting, _booking in eligible_meetings:
        try:
            result = sync_workspace_meeting_artifacts_from_google(
                db,
                workspace_id=workspace_id,
                meeting_id=meeting.id,
            )
            items.append(
                AdminClientWorkspaceMeetingArtifactBatchSyncItem(
                    meeting_id=result.meeting_id,
                    meeting_label=result.meeting_label,
                    sync_status=result.sync_status,
                    message=result.message,
                    conference_record_name=result.conference_record_name,
                    synchronized_at=result.synchronized_at,
                    artifacts_upserted=result.artifacts_upserted,
                    recordings_synced=result.recordings_synced,
                    transcripts_synced=result.transcripts_synced,
                    notes_synced=result.notes_synced,
                )
            )
            if result.sync_status == 'synchronized':
                synchronized_count += 1
            elif result.sync_status == 'no_artifacts_available':
                no_artifacts_count += 1
            elif result.sync_status == 'conference_not_found':
                conference_not_found_count += 1
        except HTTPException as exc:
            detail_text = exc.detail if isinstance(exc.detail, str) else 'Falha ao sincronizar reunião com o Google Meet.'
            items.append(
                AdminClientWorkspaceMeetingArtifactBatchSyncItem(
                    meeting_id=meeting.id,
                    meeting_label=meeting.meeting_label,
                    sync_status='failed',
                    message=detail_text,
                    conference_record_name=None,
                    synchronized_at=_iso(_now_local()) or '',
                    artifacts_upserted=0,
                    recordings_synced=0,
                    transcripts_synced=0,
                    notes_synced=0,
                )
            )
            failed_count += 1

    return AdminClientWorkspaceMeetingArtifactBatchSyncResponse(
        workspace_id=workspace.id,
        processed_meetings_count=len(items),
        eligible_meetings_count=len(eligible_meetings),
        synchronized_meetings_count=synchronized_count,
        no_artifacts_available_count=no_artifacts_count,
        conference_not_found_count=conference_not_found_count,
        failed_meetings_count=failed_count,
        items=items,
    )

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
