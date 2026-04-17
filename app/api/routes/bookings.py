from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.bookings import (
    BookingEmailConfirmationResponse,
    BookingRequestCreate,
    BookingRequestCreated,
    BookingSlotListResponse,
)
from app.services.booking_confirmations import confirm_booking_request_email
from app.services.booking_requests import create_booking_request
from app.services.booking_slots import list_dynamic_booking_slots

router = APIRouter(prefix="/bookings", tags=["bookings"])


@router.get("/health")
def bookings_healthcheck() -> dict[str, str]:
    return {
        "status": "ok",
        "module": "bookings",
    }


@router.get("/slots", response_model=BookingSlotListResponse)
def list_booking_slots(
    db: Session = Depends(get_db),
) -> BookingSlotListResponse:
    return BookingSlotListResponse(slots=list_dynamic_booking_slots(db=db))


@router.post("/requests", response_model=BookingRequestCreated)
def create_booking_request_route(
    payload: BookingRequestCreate,
    db: Session = Depends(get_db),
) -> BookingRequestCreated:
    return create_booking_request(db=db, payload=payload)


@router.get("/confirm/{token}", response_model=BookingEmailConfirmationResponse)
def confirm_booking_request_route(
    token: str,
    db: Session = Depends(get_db),
) -> BookingEmailConfirmationResponse:
    return confirm_booking_request_email(db=db, raw_token=token)