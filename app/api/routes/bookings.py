from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.bookings import (
    BookingRequestCreate,
    BookingRequestCreated,
    BookingSlotListResponse,
    BookingSlotSummary,
)
from app.services.booking_requests import create_booking_request
from app.services.booking_slots import list_static_booking_slots

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
def create_booking_request_route(
    payload: BookingRequestCreate,
    db: Session = Depends(get_db),
) -> BookingRequestCreated:
    return create_booking_request(db=db, payload=payload)