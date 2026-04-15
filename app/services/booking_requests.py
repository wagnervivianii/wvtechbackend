from fastapi import HTTPException, status

from app.schemas.bookings import (
    BookingRequestCreate,
    BookingRequestCreated,
    BookingSlotSummary,
)
from app.services.booking_slots import get_static_booking_slot_by_id


def create_static_booking_request(
    payload: BookingRequestCreate,
) -> BookingRequestCreated:
    selected_slot = get_static_booking_slot_by_id(payload.slot_id)

    if selected_slot is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Horário selecionado não encontrado",
        )

    return BookingRequestCreated(
        status="received",
        message="Solicitação recebida com sucesso",
        slot_id=payload.slot_id,
        name=payload.name,
        email=payload.email,
        phone=payload.phone,
        subject_summary=payload.subject_summary,
        slot=BookingSlotSummary(**selected_slot),
    )