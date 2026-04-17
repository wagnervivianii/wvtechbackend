from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.security import require_admin_auth
from app.db.session import get_db
from app.schemas.admin_bookings import (
    AdminBookingRebookingPermissionRequest,
    AdminBookingRebookingPermissionResponse,
)
from app.services.admin_bookings import update_rebooking_permission

router = APIRouter(
    prefix="/admin/bookings",
    tags=["admin-bookings"],
    dependencies=[Depends(require_admin_auth)],
)


@router.patch(
    "/{booking_id}/rebooking-permission",
    response_model=AdminBookingRebookingPermissionResponse,
)
def patch_booking_rebooking_permission(
    booking_id: int,
    payload: AdminBookingRebookingPermissionRequest,
    db: Session = Depends(get_db),
) -> AdminBookingRebookingPermissionResponse:
    return update_rebooking_permission(
        db=db,
        booking_id=booking_id,
        payload=payload,
    )