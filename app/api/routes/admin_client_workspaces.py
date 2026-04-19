from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.security import require_admin_auth
from app.db.session import get_db
from app.schemas.admin_client_workspaces import (
    AdminClientWorkspaceDetailResponse,
    AdminClientWorkspaceListResponse,
    AdminClientWorkspaceProvisionRequest,
)
from app.services.admin_client_workspaces import (
    get_client_workspace_by_booking,
    list_client_workspaces,
    provision_client_workspace_for_booking,
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