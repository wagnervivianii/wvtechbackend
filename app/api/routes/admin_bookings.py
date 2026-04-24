from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.security import require_admin_auth
from app.db.session import get_db
from app.schemas.admin_bookings import (
    AdminBookingApprovalRequest,
    AdminBookingCancellationRequest,
    AdminBookingDecisionResponse,
    AdminBookingPendingReviewListResponse,
    AdminBookingRebookingPermissionRequest,
    AdminBookingRebookingPermissionResponse,
    AdminBookingRejectionRequest,
    AdminBookingWhatsAppReminderDispatchRequest,
    AdminBookingWhatsAppReminderDispatchResponse,
    AdminBookingWhatsAppSendResponse,
)
from app.services.admin_bookings import (
    approve_booking_request,
    cancel_booking_request,
    get_booking_detail,
    list_pending_admin_review,
    process_due_whatsapp_reminders,
    reject_booking_request,
    send_booking_approved_whatsapp_notification,
    update_rebooking_permission,
)

router = APIRouter(
    prefix="/admin/bookings",
    tags=["admin-bookings"],
    dependencies=[Depends(require_admin_auth)],
)


@router.get("/pending-review", response_model=AdminBookingPendingReviewListResponse)
def get_pending_admin_review(
    db: Session = Depends(get_db),
) -> AdminBookingPendingReviewListResponse:
    return list_pending_admin_review(db=db)




@router.get('/{booking_id}', response_model=AdminBookingDecisionResponse)
def get_booking_decision_detail(
    booking_id: int,
    db: Session = Depends(get_db),
) -> AdminBookingDecisionResponse:
    return get_booking_detail(
        db=db,
        booking_id=booking_id,
    )


@router.post('/{booking_id}/whatsapp/send-approved', response_model=AdminBookingWhatsAppSendResponse)
def post_booking_whatsapp_send_approved(
    booking_id: int,
    db: Session = Depends(get_db),
) -> AdminBookingWhatsAppSendResponse:
    return send_booking_approved_whatsapp_notification(
        db=db,
        booking_id=booking_id,
    )


@router.post('/whatsapp/process-reminders', response_model=AdminBookingWhatsAppReminderDispatchResponse)
def post_process_due_whatsapp_reminders(
    payload: AdminBookingWhatsAppReminderDispatchRequest,
    db: Session = Depends(get_db),
) -> AdminBookingWhatsAppReminderDispatchResponse:
    return process_due_whatsapp_reminders(
        db=db,
        payload=payload,
    )

@router.post("/{booking_id}/approve", response_model=AdminBookingDecisionResponse)
def post_booking_approval(
    booking_id: int,
    payload: AdminBookingApprovalRequest,
    db: Session = Depends(get_db),
) -> AdminBookingDecisionResponse:
    return approve_booking_request(
        db=db,
        booking_id=booking_id,
        payload=payload,
    )


@router.post("/{booking_id}/reject", response_model=AdminBookingDecisionResponse)
def post_booking_rejection(
    booking_id: int,
    payload: AdminBookingRejectionRequest,
    db: Session = Depends(get_db),
) -> AdminBookingDecisionResponse:
    return reject_booking_request(
        db=db,
        booking_id=booking_id,
        payload=payload,
    )


@router.post("/{booking_id}/cancel", response_model=AdminBookingDecisionResponse)
def post_booking_cancellation(
    booking_id: int,
    payload: AdminBookingCancellationRequest,
    db: Session = Depends(get_db),
) -> AdminBookingDecisionResponse:
    return cancel_booking_request(
        db=db,
        booking_id=booking_id,
        payload=payload,
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