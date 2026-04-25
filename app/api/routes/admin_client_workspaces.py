from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from sqlalchemy.orm import Session

from app.core.rate_limit import rate_limit_admin_write
from app.core.security import require_admin_auth
from app.db.session import get_db
from app.schemas.admin_client_workspaces import (
    AdminClientWorkspaceArtifactUpsertRequest,
    AdminClientWorkspaceArtifactsResponse,
    AdminClientWorkspaceDetailResponse,
    AdminClientWorkspaceFileActionRequest,
    AdminClientWorkspaceFileItem,
    AdminClientWorkspaceFileListResponse,
    AdminClientWorkspaceMeetingArtifactBatchSyncRequest,
    AdminClientWorkspaceMeetingArtifactBatchSyncResponse,
    AdminClientWorkspaceInviteRefreshRequest,
    AdminClientWorkspaceListResponse,
    AdminClientWorkspaceMeetingArtifactItem,
    AdminClientWorkspaceMeetingArtifactSyncResponse,
    AdminClientWorkspaceProvisionRequest,
)
from app.services.admin_client_workspaces import (
    get_client_workspace_by_booking,
    list_client_workspaces,
    provision_client_workspace_for_booking,
    regenerate_client_workspace_invite,
    sync_client_workspace_drive_folders,
)
from app.services.client_workspace_artifacts import (
    get_workspace_artifacts_for_admin,
    sync_workspace_meeting_artifacts_from_google,
    sync_workspace_pending_google_artifacts,
    upsert_workspace_meeting_artifact,
)
from app.services.client_workspace_files import (
    admin_upload_workspace_file,
    approve_workspace_file,
    archive_workspace_file,
    delete_workspace_file,
    list_admin_workspace_files,
    read_upload_file,
    reject_workspace_file,
)

router = APIRouter(
    prefix="/admin",
    tags=["admin-client-workspaces"],
    dependencies=[Depends(require_admin_auth)],
)


@router.get("/client-workspaces", response_model=AdminClientWorkspaceListResponse)
def get_admin_client_workspaces(
    db: Session = Depends(get_db),
) -> AdminClientWorkspaceListResponse:
    return list_client_workspaces(db=db)


@router.post("/bookings/{booking_id}/client-workspace", response_model=AdminClientWorkspaceDetailResponse)
def post_admin_client_workspace_for_booking(
    booking_id: int,
    payload: AdminClientWorkspaceProvisionRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> AdminClientWorkspaceDetailResponse:
    rate_limit_admin_write(request)
    return provision_client_workspace_for_booking(
        db=db,
        booking_id=booking_id,
        payload=payload,
    )


@router.get("/bookings/{booking_id}/client-workspace", response_model=AdminClientWorkspaceDetailResponse)
def get_admin_client_workspace_for_booking(
    booking_id: int,
    db: Session = Depends(get_db),
) -> AdminClientWorkspaceDetailResponse:
    return get_client_workspace_by_booking(
        db=db,
        booking_id=booking_id,
    )


@router.post("/client-workspaces/{workspace_id}/invite", response_model=AdminClientWorkspaceDetailResponse)
def post_admin_client_workspace_invite(
    workspace_id: int,
    payload: AdminClientWorkspaceInviteRefreshRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> AdminClientWorkspaceDetailResponse:
    rate_limit_admin_write(request)
    return regenerate_client_workspace_invite(
        db=db,
        workspace_id=workspace_id,
        payload=payload,
    )


@router.post("/client-workspaces/{workspace_id}/drive-sync", response_model=AdminClientWorkspaceDetailResponse)
def post_admin_client_workspace_drive_sync(
    workspace_id: int,
    request: Request,
    db: Session = Depends(get_db),
) -> AdminClientWorkspaceDetailResponse:
    rate_limit_admin_write(request)
    return sync_client_workspace_drive_folders(
        db=db,
        workspace_id=workspace_id,
    )


@router.get("/client-workspaces/{workspace_id}/artifacts", response_model=AdminClientWorkspaceArtifactsResponse)
def get_admin_client_workspace_artifacts(
    workspace_id: int,
    db: Session = Depends(get_db),
) -> AdminClientWorkspaceArtifactsResponse:
    workspaces = list_client_workspaces(db=db)
    workspace_item = next((item for item in workspaces.items if item.workspace_id == workspace_id), None)
    if workspace_item is None:
        from fastapi import HTTPException, status
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail='Workspace do cliente não encontrado.',
        )
    return get_workspace_artifacts_for_admin(
        db=db,
        workspace_id=workspace_id,
        meetings=workspace_item.meetings,
    )


@router.post(
    "/client-workspaces/{workspace_id}/meetings/{meeting_id}/artifacts",
    response_model=AdminClientWorkspaceMeetingArtifactItem,
)
def post_admin_client_workspace_meeting_artifact(
    workspace_id: int,
    meeting_id: int,
    payload: AdminClientWorkspaceArtifactUpsertRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> AdminClientWorkspaceMeetingArtifactItem:
    rate_limit_admin_write(request)
    return upsert_workspace_meeting_artifact(
        db=db,
        workspace_id=workspace_id,
        meeting_id=meeting_id,
        payload=payload,
    )


@router.post(
    "/client-workspaces/{workspace_id}/meetings/{meeting_id}/artifacts/sync-google",
    response_model=AdminClientWorkspaceMeetingArtifactSyncResponse,
)
def post_admin_client_workspace_meeting_artifact_google_sync(
    workspace_id: int,
    meeting_id: int,
    request: Request,
    db: Session = Depends(get_db),
) -> AdminClientWorkspaceMeetingArtifactSyncResponse:
    rate_limit_admin_write(request)
    return sync_workspace_meeting_artifacts_from_google(
        db=db,
        workspace_id=workspace_id,
        meeting_id=meeting_id,
    )


@router.post(
    "/client-workspaces/{workspace_id}/artifacts/sync-google-pending",
    response_model=AdminClientWorkspaceMeetingArtifactBatchSyncResponse,
)
def post_admin_client_workspace_pending_google_artifacts_sync(
    workspace_id: int,
    payload: AdminClientWorkspaceMeetingArtifactBatchSyncRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> AdminClientWorkspaceMeetingArtifactBatchSyncResponse:
    rate_limit_admin_write(request)
    return sync_workspace_pending_google_artifacts(
        db=db,
        workspace_id=workspace_id,
        payload=payload,
    )


@router.get("/client-workspaces/{workspace_id}/files", response_model=AdminClientWorkspaceFileListResponse)
def get_admin_client_workspace_files(
    workspace_id: int,
    db: Session = Depends(get_db),
) -> AdminClientWorkspaceFileListResponse:
    return list_admin_workspace_files(db=db, workspace_id=workspace_id)


@router.post("/client-workspaces/{workspace_id}/files/admin-upload", response_model=AdminClientWorkspaceFileItem)
async def post_admin_client_workspace_file_upload(
    workspace_id: int,
    request: Request,
    file: UploadFile = File(...),
    meeting_id: int | None = Form(None),
    display_name: str | None = Form(None),
    description: str | None = Form(None),
    file_category: str = Form('generated_document'),
    target_bucket: str = Form('generated_documents'),
    visible_to_client: bool = Form(True),
    db: Session = Depends(get_db),
) -> AdminClientWorkspaceFileItem:
    rate_limit_admin_write(request)
    prepared = await read_upload_file(file)
    return admin_upload_workspace_file(
        db=db,
        workspace_id=workspace_id,
        upload=prepared,
        meeting_id=meeting_id,
        display_name=display_name,
        description=description,
        file_category=file_category,
        target_bucket=target_bucket,
        visible_to_client=visible_to_client,
    )


@router.post("/client-workspaces/{workspace_id}/files/{file_id}/approve", response_model=AdminClientWorkspaceFileItem)
def post_admin_client_workspace_file_approve(
    workspace_id: int,
    file_id: int,
    payload: AdminClientWorkspaceFileActionRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> AdminClientWorkspaceFileItem:
    rate_limit_admin_write(request)
    return approve_workspace_file(db=db, workspace_id=workspace_id, file_id=file_id, payload=payload)


@router.post("/client-workspaces/{workspace_id}/files/{file_id}/reject", response_model=AdminClientWorkspaceFileItem)
def post_admin_client_workspace_file_reject(
    workspace_id: int,
    file_id: int,
    payload: AdminClientWorkspaceFileActionRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> AdminClientWorkspaceFileItem:
    rate_limit_admin_write(request)
    return reject_workspace_file(db=db, workspace_id=workspace_id, file_id=file_id, payload=payload)


@router.post("/client-workspaces/{workspace_id}/files/{file_id}/archive", response_model=AdminClientWorkspaceFileItem)
def post_admin_client_workspace_file_archive(
    workspace_id: int,
    file_id: int,
    payload: AdminClientWorkspaceFileActionRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> AdminClientWorkspaceFileItem:
    rate_limit_admin_write(request)
    return archive_workspace_file(db=db, workspace_id=workspace_id, file_id=file_id, payload=payload)


@router.post("/client-workspaces/{workspace_id}/files/{file_id}/delete", response_model=AdminClientWorkspaceFileItem)
def delete_admin_client_workspace_file(
    workspace_id: int,
    file_id: int,
    payload: AdminClientWorkspaceFileActionRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> AdminClientWorkspaceFileItem:
    rate_limit_admin_write(request)
    return delete_workspace_file(db=db, workspace_id=workspace_id, file_id=file_id, payload=payload)
