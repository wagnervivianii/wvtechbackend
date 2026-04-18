from __future__ import annotations

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.booking_request import BookingRequest
from app.services.booking_request_status import REOPENED_BOOKING_REQUEST_STATUSES


def booking_request_locks_contact(booking_request: BookingRequest) -> bool:
    if booking_request.can_schedule_again:
        return False

    return booking_request.status not in REOPENED_BOOKING_REQUEST_STATUSES


def find_latest_contact_lock(
    db: Session,
    *,
    email: str,
    phone: str,
) -> BookingRequest | None:
    bookings = db.scalars(
        select(BookingRequest)
        .where(
            or_(
                BookingRequest.email == email,
                BookingRequest.phone == phone,
            )
        )
        .order_by(BookingRequest.created_at.desc(), BookingRequest.id.desc())
    ).all()

    for booking in bookings:
        if booking_request_locks_contact(booking):
            return booking

    return None