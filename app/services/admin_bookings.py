from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.booking_request import BookingRequest
from app.schemas.admin_bookings import (
    AdminBookingRebookingPermissionRequest,
    AdminBookingRebookingPermissionResponse,
)
from app.services.booking_request_status import REOPENED_BOOKING_REQUEST_STATUSES

TERMINAL_MEETING_STATUSES = {"completed", "cancelled", "no_show"}


def _booking_has_already_happened(booking: BookingRequest) -> bool:
    if booking.status in REOPENED_BOOKING_REQUEST_STATUSES:
        return True

    if booking.meeting_status in TERMINAL_MEETING_STATUSES:
        return True

    if booking.booking_date is None:
        return False

    now_local = datetime.now(ZoneInfo(settings.app_timezone))

    if booking.end_time is not None:
        booking_end = datetime.combine(
            booking.booking_date,
            booking.end_time,
            tzinfo=ZoneInfo(settings.app_timezone),
        )
        return booking_end <= now_local

    if booking.start_time is not None:
        booking_start = datetime.combine(
            booking.booking_date,
            booking.start_time,
            tzinfo=ZoneInfo(settings.app_timezone),
        )
        return booking_start <= now_local

    return booking.booking_date < now_local.date()


def update_rebooking_permission(
    db: Session,
    *,
    booking_id: int,
    payload: AdminBookingRebookingPermissionRequest,
) -> AdminBookingRebookingPermissionResponse:
    booking = db.get(BookingRequest, booking_id)
    if booking is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Solicitação de reunião não encontrada.",
        )

    if payload.can_schedule_again and not _booking_has_already_happened(booking):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "A liberação de novo agendamento só pode acontecer depois que a reunião "
                "anterior já tiver ocorrido ou sido encerrada manualmente."
            ),
        )

    booking.can_schedule_again = payload.can_schedule_again
    db.add(booking)
    db.commit()
    db.refresh(booking)

    return AdminBookingRebookingPermissionResponse(
        id=booking.id,
        status=booking.status,
        meeting_status=booking.meeting_status,
        email=booking.email,
        phone=booking.phone,
        can_schedule_again=booking.can_schedule_again,
    )