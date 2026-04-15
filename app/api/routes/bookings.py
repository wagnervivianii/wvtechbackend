from fastapi import APIRouter, HTTPException, status

from app.schemas.bookings import BookingRequestCreate, BookingRequestCreated

router = APIRouter(prefix="/bookings", tags=["bookings"])

STATIC_SLOTS = [
    {
        "id": "slot-1",
        "date": "2026-04-20",
        "start_time": "09:00",
        "end_time": "09:30",
        "label": "20/04/2026 • 09:00 às 09:30",
    },
    {
        "id": "slot-2",
        "date": "2026-04-20",
        "start_time": "10:00",
        "end_time": "10:30",
        "label": "20/04/2026 • 10:00 às 10:30",
    },
    {
        "id": "slot-3",
        "date": "2026-04-21",
        "start_time": "14:00",
        "end_time": "14:30",
        "label": "21/04/2026 • 14:00 às 14:30",
    },
]


@router.get("/health")
def bookings_healthcheck() -> dict[str, str]:
    return {
        "status": "ok",
        "module": "bookings",
    }


@router.get("/slots")
def list_booking_slots() -> dict[str, list[dict[str, str]]]:
    return {
        "slots": STATIC_SLOTS,
    }


def get_slot_by_id(slot_id: str) -> dict[str, str] | None:
    for slot in STATIC_SLOTS:
        if slot["id"] == slot_id:
            return slot
    return None


@router.post("/requests", response_model=BookingRequestCreated)
def create_booking_request(payload: BookingRequestCreate) -> BookingRequestCreated:
    selected_slot = get_slot_by_id(payload.slot_id)

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
    )