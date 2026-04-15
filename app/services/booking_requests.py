from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.booking_request import BookingRequest
from app.schemas.bookings import (
    BookingRequestCreate,
    BookingRequestCreated,
    BookingSlotSummary,
)
from app.services.booking_slots import get_static_booking_slot_by_id


def create_booking_request(
    db: Session,
    payload: BookingRequestCreate,
) -> BookingRequestCreated:
    selected_slot = get_static_booking_slot_by_id(payload.slot_id)

    if selected_slot is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Horário selecionado não encontrado",
        )

    booking_request = BookingRequest(
        slot_id=payload.slot_id,
        name=payload.name,
        email=payload.email,
        phone=payload.phone,
        subject_summary=payload.subject_summary,
        status="received",
    )

    db.add(booking_request)
    db.commit()
    db.refresh(booking_request)

    return BookingRequestCreated(
        status=booking_request.status,
        message="Solicitação recebida com sucesso",
        slot_id=booking_request.slot_id,
        name=booking_request.name,
        email=booking_request.email,
        phone=booking_request.phone,
        subject_summary=booking_request.subject_summary,
        slot=BookingSlotSummary(**selected_slot),
    )