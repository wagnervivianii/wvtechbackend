from fastapi import APIRouter, HTTPException, status

from app.schemas.bookings import (
    BookingRequestCreate,
    BookingRequestCreated,
    BookingSlotListResponse,
    BookingSlotSummary,
)
from app.services.booking_slots import (
    get_static_booking_slot_by_id,
    list_static_booking_slots,
)

router = APIRouter(prefix="/bookings", tags=["bookings"])


@router.get("/health")
def bookings_healthcheck() -> dict[str, str]:
    return {
        "status": "ok",
        "module": "bookings",
    }


@router.get("/slots", response_model=BookingSlotListResponse)
def list_booking_slots() -> BookingSlotListResponse:
    slots = [BookingSlotSummary(**slot) for slot in list_static_booking_slots()]
    return BookingSlotListResponse(slots=slots)


@router.post("/requests", response_model=BookingRequestCreated)
def create_booking_request(payload: BookingRequestCreate) -> BookingRequestCreated:
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