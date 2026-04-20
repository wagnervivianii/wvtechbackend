from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.security import require_admin_auth
from app.db.session import get_db
from app.schemas.admin_client_workspaces import (
    AdminClientWorkspaceArtifactUpsertRequest,
    AdminClientWorkspaceArtifactsResponse,
    AdminClientWorkspaceDetailResponse,
    AdminClientWorkspaceInviteRefreshRequest,
    AdminClientWorkspaceListResponse,
    AdminClientWorkspaceMeetingArtifactItem,
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
    upsert_workspace_meeting_artifact,
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
    db: Session = Depends(get_db),
) -> AdminClientWorkspaceDetailResponse:
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
    db: Session = Depends(get_db),
) -> AdminClientWorkspaceDetailResponse:
    return regenerate_client_workspace_invite(
        db=db,
        workspace_id=workspace_id,
        payload=payload,
    )


@router.post("/client-workspaces/{workspace_id}/drive-sync", response_model=AdminClientWorkspaceDetailResponse)
def post_admin_client_workspace_drive_sync(
    workspace_id: int,
    db: Session = Depends(get_db),
) -> AdminClientWorkspaceDetailResponse:
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
    db: Session = Depends(get_db),
) -> AdminClientWorkspaceMeetingArtifactItem:
    return upsert_workspace_meeting_artifact(
        db=db,
        workspace_id=workspace_id,
        meeting_id=meeting_id,
        payload=payload,
    )
