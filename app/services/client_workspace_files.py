from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import hashlib
from pathlib import Path
from zoneinfo import ZoneInfo

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.client_workspace import ClientWorkspace
from app.models.client_workspace_account import ClientWorkspaceAccount
from app.models.client_workspace_file import ClientWorkspaceFile
from app.models.client_workspace_meeting import ClientWorkspaceMeeting
from app.schemas.admin_client_workspaces import (
    AdminClientWorkspaceFileActionRequest,
    AdminClientWorkspaceFileItem,
    AdminClientWorkspaceFileListResponse,
)
from app.schemas.client_portal import (
    ClientPortalWorkspaceFileItem,
    ClientPortalWorkspaceFilesResponse,
    ClientPortalWorkspaceFileUploadResponse,
)
from app.services.client_auth import get_authenticated_client_context
from app.services.google_drive import (
    GoogleDriveIntegrationError,
    GoogleDriveIntegrationNotConfiguredError,
    ensure_client_workspace_drive_folders,
    is_google_drive_workspace_storage_configured,
    move_google_drive_file_to_folder,
    trash_google_drive_file,
    upload_bytes_to_google_drive_folder,
)

ALLOWED_EXTENSIONS = {'.pdf', '.xls', '.xlsx', '.csv', '.ppt', '.pptx', '.doc', '.docx', '.txt'}
ALLOWED_CATEGORIES = {'client_upload', 'admin_material', 'generated_document'}
ALLOWED_TARGET_BUCKETS = {'client_uploads', 'generated_documents', 'archive'}

PENDING_REVIEW = 'pending_review'
APPROVED = 'approved'
REJECTED = 'rejected'
ARCHIVED = 'archived'
DELETED = 'deleted'

CLIENT_VISIBLE = 'client_visible'
ADMIN_ONLY = 'admin_only'


@dataclass(frozen=True, slots=True)
class PreparedUpload:
    file_name: str
    mime_type: str | None
    file_extension: str
    file_size_bytes: int
    checksum_sha256: str
    file_bytes: bytes


def _now_local() -> datetime:
    return datetime.now(ZoneInfo(settings.app_timezone))


def _normalize_extension(file_name: str) -> str:
    return Path(file_name).suffix.strip().lower()


def _validate_file_extension(file_name: str) -> str:
    extension = _normalize_extension(file_name)
    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail='Tipo de arquivo não permitido. Use PDF, Excel, PowerPoint, Word ou TXT.',
        )
    return extension


def _prepare_upload(file_name: str, file_bytes: bytes, mime_type: str | None) -> PreparedUpload:
    if not file_name.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail='Nome do arquivo inválido.',
        )
    if not file_bytes:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail='O arquivo enviado está vazio.',
        )
    if len(file_bytes) > settings.google_drive_direct_upload_max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail='O arquivo excede o limite configurado para upload direto ao Google Drive.',
        )
    extension = _validate_file_extension(file_name)
    checksum = hashlib.sha256(file_bytes).hexdigest()
    return PreparedUpload(
        file_name=file_name.strip(),
        mime_type=mime_type,
        file_extension=extension,
        file_size_bytes=len(file_bytes),
        checksum_sha256=checksum,
        file_bytes=file_bytes,
    )


async def read_upload_file(upload: UploadFile) -> PreparedUpload:
    file_bytes = await upload.read()
    return _prepare_upload(upload.filename or 'arquivo', file_bytes, upload.content_type)


def _get_workspace_or_404(db: Session, workspace_id: int) -> ClientWorkspace:
    workspace = db.get(ClientWorkspace, workspace_id)
    if workspace is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Workspace do cliente não encontrado.')
    return workspace


def _get_workspace_meeting_or_404(db: Session, workspace_id: int, meeting_id: int | None) -> ClientWorkspaceMeeting | None:
    if meeting_id is None:
        return None
    meeting = db.get(ClientWorkspaceMeeting, meeting_id)
    if meeting is None or meeting.workspace_id != workspace_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Reunião do workspace não encontrada.')
    return meeting


def _get_workspace_file_or_404(db: Session, workspace_id: int, file_id: int) -> ClientWorkspaceFile:
    file = db.get(ClientWorkspaceFile, file_id)
    if file is None or file.workspace_id != workspace_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Arquivo do workspace não encontrado.')
    return file


def _workspace_drive_ready(workspace: ClientWorkspace) -> bool:
    return bool(
        workspace.drive_root_folder_id
        and workspace.drive_client_uploads_folder_id
        and workspace.drive_generated_documents_folder_id
        and workspace.drive_archive_folder_id
    )


def _ensure_workspace_drive_structure(db: Session, workspace: ClientWorkspace) -> None:
    if _workspace_drive_ready(workspace):
        return
    if not is_google_drive_workspace_storage_configured():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail='Estrutura Google Drive do workspace ainda não está pronta.',
        )
    try:
        folders = ensure_client_workspace_drive_folders(
            workspace_id=workspace.id,
            primary_contact_name=workspace.primary_contact_name,
            existing_root_folder_id=workspace.drive_root_folder_id,
        )
    except GoogleDriveIntegrationNotConfiguredError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except GoogleDriveIntegrationError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f'Não foi possível preparar a estrutura do Drive. {exc}') from exc

    workspace.drive_root_folder_id = folders.root.folder_id
    workspace.drive_root_folder_name = folders.root.folder_name
    workspace.drive_root_folder_url = folders.root.web_view_link
    workspace.drive_client_uploads_folder_id = folders.client_uploads.folder_id
    workspace.drive_client_uploads_folder_name = folders.client_uploads.folder_name
    workspace.drive_client_uploads_folder_url = folders.client_uploads.web_view_link
    workspace.drive_generated_documents_folder_id = folders.generated_documents.folder_id
    workspace.drive_generated_documents_folder_name = folders.generated_documents.folder_name
    workspace.drive_generated_documents_folder_url = folders.generated_documents.web_view_link
    workspace.drive_archive_folder_id = folders.archive.folder_id
    workspace.drive_archive_folder_name = folders.archive.folder_name
    workspace.drive_archive_folder_url = folders.archive.web_view_link
    workspace.drive_sync_status = 'ready'
    workspace.drive_sync_error = None
    workspace.drive_synced_at = _now_local()
    db.add(workspace)
    db.flush()


def _resolve_target_folder_id(workspace: ClientWorkspace, bucket: str) -> str:
    if bucket == 'client_uploads' and workspace.drive_client_uploads_folder_id:
        return workspace.drive_client_uploads_folder_id
    if bucket == 'generated_documents' and workspace.drive_generated_documents_folder_id:
        return workspace.drive_generated_documents_folder_id
    if bucket == 'archive' and workspace.drive_archive_folder_id:
        return workspace.drive_archive_folder_id
    raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail='A pasta de destino no Google Drive ainda não está pronta.')


def _serialize_admin_file(item: ClientWorkspaceFile) -> AdminClientWorkspaceFileItem:
    return AdminClientWorkspaceFileItem(
        id=item.id,
        workspace_id=item.workspace_id,
        meeting_id=item.meeting_id,
        uploaded_by_role=item.uploaded_by_role,
        file_category=item.file_category,
        review_status=item.review_status,
        visibility_scope=item.visibility_scope,
        display_name=item.display_name,
        description=item.description,
        drive_file_id=item.drive_file_id,
        drive_file_name=item.drive_file_name,
        drive_web_view_link=item.drive_web_view_link,
        mime_type=item.mime_type,
        file_extension=item.file_extension,
        file_size_bytes=item.file_size_bytes,
        review_notes=item.review_notes,
        approved_at=item.approved_at.isoformat() if item.approved_at else None,
        reviewed_at=item.reviewed_at.isoformat() if item.reviewed_at else None,
        archived_at=item.archived_at.isoformat() if item.archived_at else None,
        deleted_at=item.deleted_at.isoformat() if item.deleted_at else None,
        created_at=item.created_at.isoformat(),
        updated_at=item.updated_at.isoformat(),
    )


def _serialize_client_file(item: ClientWorkspaceFile) -> ClientPortalWorkspaceFileItem:
    return ClientPortalWorkspaceFileItem(
        id=item.id,
        meeting_id=item.meeting_id,
        file_category=item.file_category,
        display_name=item.display_name,
        description=item.description,
        drive_file_name=item.drive_file_name,
        drive_web_view_link=item.drive_web_view_link,
        mime_type=item.mime_type,
        file_extension=item.file_extension,
        file_size_bytes=item.file_size_bytes,
        created_at=item.created_at.isoformat(),
    )


def _create_file_record(
    db: Session,
    *,
    workspace: ClientWorkspace,
    meeting: ClientWorkspaceMeeting | None,
    prepared: PreparedUpload,
    uploaded_by_role: str,
    uploaded_by_account_id: int | None,
    file_category: str,
    visibility_scope: str,
    review_status: str,
    display_name: str | None,
    description: str | None,
    drive_file_id: str,
    drive_file_name: str | None,
    drive_web_view_link: str | None,
    drive_folder_id: str | None,
) -> ClientWorkspaceFile:
    item = ClientWorkspaceFile(
        workspace_id=workspace.id,
        meeting_id=meeting.id if meeting else None,
        uploaded_by_role=uploaded_by_role,
        uploaded_by_account_id=uploaded_by_account_id,
        file_category=file_category,
        review_status=review_status,
        visibility_scope=visibility_scope,
        display_name=display_name or drive_file_name or prepared.file_name,
        description=description,
        drive_file_id=drive_file_id,
        drive_file_name=drive_file_name or prepared.file_name,
        drive_web_view_link=drive_web_view_link,
        drive_folder_id=drive_folder_id,
        mime_type=prepared.mime_type,
        file_extension=prepared.file_extension,
        file_size_bytes=prepared.file_size_bytes,
        checksum_sha256=prepared.checksum_sha256,
        approved_at=_now_local() if review_status == APPROVED else None,
        reviewed_at=_now_local() if review_status != PENDING_REVIEW else None,
    )
    db.add(item)
    db.flush()
    return item


def list_admin_workspace_files(db: Session, *, workspace_id: int) -> AdminClientWorkspaceFileListResponse:
    workspace = _get_workspace_or_404(db, workspace_id)
    items = db.scalars(
        select(ClientWorkspaceFile)
        .where(ClientWorkspaceFile.workspace_id == workspace.id)
        .order_by(ClientWorkspaceFile.created_at.desc(), ClientWorkspaceFile.id.desc())
    ).all()
    return AdminClientWorkspaceFileListResponse(
        workspace_id=workspace.id,
        pending_review_count=sum(1 for item in items if item.review_status == PENDING_REVIEW),
        approved_count=sum(1 for item in items if item.review_status == APPROVED),
        archived_count=sum(1 for item in items if item.review_status == ARCHIVED),
        rejected_count=sum(1 for item in items if item.review_status == REJECTED),
        items=[_serialize_admin_file(item) for item in items],
    )


def list_client_workspace_files(db: Session, claims: dict[str, object]) -> ClientPortalWorkspaceFilesResponse:
    context = get_authenticated_client_context(db, claims)
    items = db.scalars(
        select(ClientWorkspaceFile)
        .where(ClientWorkspaceFile.workspace_id == context.workspace.id)
        .where(ClientWorkspaceFile.review_status == APPROVED)
        .where(ClientWorkspaceFile.visibility_scope == CLIENT_VISIBLE)
        .where(ClientWorkspaceFile.deleted_at.is_(None))
        .order_by(ClientWorkspaceFile.created_at.desc(), ClientWorkspaceFile.id.desc())
    ).all()
    return ClientPortalWorkspaceFilesResponse(
        workspace_id=context.workspace.id,
        items=[_serialize_client_file(item) for item in items],
    )


def client_upload_workspace_file(
    db: Session,
    *,
    claims: dict[str, object],
    upload: PreparedUpload,
    meeting_id: int | None,
    display_name: str | None,
    description: str | None,
) -> ClientPortalWorkspaceFileUploadResponse:
    context = get_authenticated_client_context(db, claims)
    workspace = context.workspace
    _ensure_workspace_drive_structure(db, workspace)
    meeting = _get_workspace_meeting_or_404(db, workspace.id, meeting_id)
    folder_id = _resolve_target_folder_id(workspace, 'archive')
    try:
        drive_file = upload_bytes_to_google_drive_folder(
            folder_id=folder_id,
            file_name=upload.file_name,
            file_bytes=upload.file_bytes,
            mime_type=upload.mime_type,
        )
    except GoogleDriveIntegrationError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f'Não foi possível enviar o arquivo ao Google Drive. {exc}') from exc

    item = _create_file_record(
        db,
        workspace=workspace,
        meeting=meeting,
        prepared=upload,
        uploaded_by_role='client',
        uploaded_by_account_id=context.account.id,
        file_category='client_upload',
        visibility_scope=ADMIN_ONLY,
        review_status=PENDING_REVIEW,
        display_name=display_name,
        description=description,
        drive_file_id=drive_file.file_id,
        drive_file_name=drive_file.file_name,
        drive_web_view_link=drive_file.web_view_link,
        drive_folder_id=folder_id,
    )
    db.commit()
    db.refresh(item)
    return ClientPortalWorkspaceFileUploadResponse(
        message='Arquivo enviado para análise administrativa com sucesso.',
        item=_serialize_client_file(item),
        review_status=item.review_status,
    )


def admin_upload_workspace_file(
    db: Session,
    *,
    workspace_id: int,
    upload: PreparedUpload,
    meeting_id: int | None,
    display_name: str | None,
    description: str | None,
    file_category: str,
    target_bucket: str,
    visible_to_client: bool,
) -> AdminClientWorkspaceFileItem:
    workspace = _get_workspace_or_404(db, workspace_id)
    _ensure_workspace_drive_structure(db, workspace)
    meeting = _get_workspace_meeting_or_404(db, workspace.id, meeting_id)
    normalized_category = file_category.strip().lower()
    if normalized_category not in ALLOWED_CATEGORIES:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail='Categoria de arquivo inválida.')
    normalized_bucket = target_bucket.strip().lower()
    if normalized_bucket not in ALLOWED_TARGET_BUCKETS:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail='Pasta de destino inválida.')
    folder_id = _resolve_target_folder_id(workspace, normalized_bucket)
    try:
        drive_file = upload_bytes_to_google_drive_folder(
            folder_id=folder_id,
            file_name=upload.file_name,
            file_bytes=upload.file_bytes,
            mime_type=upload.mime_type,
        )
    except GoogleDriveIntegrationError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f'Não foi possível enviar o arquivo ao Google Drive. {exc}') from exc
    item = _create_file_record(
        db,
        workspace=workspace,
        meeting=meeting,
        prepared=upload,
        uploaded_by_role='admin',
        uploaded_by_account_id=None,
        file_category=normalized_category,
        visibility_scope=CLIENT_VISIBLE if visible_to_client else ADMIN_ONLY,
        review_status=APPROVED,
        display_name=display_name,
        description=description,
        drive_file_id=drive_file.file_id,
        drive_file_name=drive_file.file_name,
        drive_web_view_link=drive_file.web_view_link,
        drive_folder_id=folder_id,
    )
    db.commit()
    db.refresh(item)
    return _serialize_admin_file(item)


def approve_workspace_file(
    db: Session,
    *,
    workspace_id: int,
    file_id: int,
    payload: AdminClientWorkspaceFileActionRequest,
) -> AdminClientWorkspaceFileItem:
    workspace = _get_workspace_or_404(db, workspace_id)
    _ensure_workspace_drive_structure(db, workspace)
    item = _get_workspace_file_or_404(db, workspace_id, file_id)
    try:
        moved_file = move_google_drive_file_to_folder(file_id=item.drive_file_id, target_folder_id=workspace.drive_client_uploads_folder_id)
    except GoogleDriveIntegrationError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f'Não foi possível mover o arquivo para a pasta aprovada. {exc}') from exc
    now = _now_local()
    item.review_status = APPROVED
    item.visibility_scope = CLIENT_VISIBLE if payload.visible_to_client else ADMIN_ONLY
    item.review_notes = payload.review_notes
    item.approved_at = now
    item.reviewed_at = now
    item.archived_at = None
    item.drive_folder_id = workspace.drive_client_uploads_folder_id
    item.drive_file_name = moved_file.file_name
    item.drive_web_view_link = moved_file.web_view_link
    item.mime_type = moved_file.mime_type or item.mime_type
    item.file_size_bytes = moved_file.file_size_bytes or item.file_size_bytes
    db.add(item)
    db.commit()
    db.refresh(item)
    return _serialize_admin_file(item)


def reject_workspace_file(
    db: Session,
    *,
    workspace_id: int,
    file_id: int,
    payload: AdminClientWorkspaceFileActionRequest,
) -> AdminClientWorkspaceFileItem:
    workspace = _get_workspace_or_404(db, workspace_id)
    _ensure_workspace_drive_structure(db, workspace)
    item = _get_workspace_file_or_404(db, workspace_id, file_id)
    if workspace.drive_archive_folder_id and item.drive_folder_id != workspace.drive_archive_folder_id:
        try:
            moved_file = move_google_drive_file_to_folder(file_id=item.drive_file_id, target_folder_id=workspace.drive_archive_folder_id)
            item.drive_file_name = moved_file.file_name
            item.drive_web_view_link = moved_file.web_view_link
            item.drive_folder_id = workspace.drive_archive_folder_id
        except GoogleDriveIntegrationError as exc:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f'Não foi possível mover o arquivo rejeitado para o arquivo morto. {exc}') from exc
    item.review_status = REJECTED
    item.visibility_scope = ADMIN_ONLY
    item.review_notes = payload.review_notes
    item.reviewed_at = _now_local()
    db.add(item)
    db.commit()
    db.refresh(item)
    return _serialize_admin_file(item)


def archive_workspace_file(db: Session, *, workspace_id: int, file_id: int, payload: AdminClientWorkspaceFileActionRequest) -> AdminClientWorkspaceFileItem:
    workspace = _get_workspace_or_404(db, workspace_id)
    _ensure_workspace_drive_structure(db, workspace)
    item = _get_workspace_file_or_404(db, workspace_id, file_id)
    try:
        moved_file = move_google_drive_file_to_folder(file_id=item.drive_file_id, target_folder_id=workspace.drive_archive_folder_id)
    except GoogleDriveIntegrationError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f'Não foi possível arquivar o arquivo no Google Drive. {exc}') from exc
    now = _now_local()
    item.review_status = ARCHIVED
    item.visibility_scope = ADMIN_ONLY
    item.review_notes = payload.review_notes
    item.archived_at = now
    item.reviewed_at = now
    item.drive_folder_id = workspace.drive_archive_folder_id
    item.drive_file_name = moved_file.file_name
    item.drive_web_view_link = moved_file.web_view_link
    db.add(item)
    db.commit()
    db.refresh(item)
    return _serialize_admin_file(item)


def delete_workspace_file(db: Session, *, workspace_id: int, file_id: int, payload: AdminClientWorkspaceFileActionRequest) -> AdminClientWorkspaceFileItem:
    item = _get_workspace_file_or_404(db, workspace_id, file_id)
    if item.deleted_at is None:
        try:
            trash_google_drive_file(file_id=item.drive_file_id)
        except GoogleDriveIntegrationError as exc:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f'Não foi possível mover o arquivo para a lixeira do Google Drive. {exc}') from exc
        item.review_status = DELETED
        item.visibility_scope = ADMIN_ONLY
        item.review_notes = payload.review_notes
        item.deleted_at = _now_local()
        db.add(item)
        db.commit()
        db.refresh(item)
    return _serialize_admin_file(item)
