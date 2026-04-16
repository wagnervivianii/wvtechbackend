from sqlalchemy.orm import Session

from app.schemas.bookings import BookingSlotSummary
from app.services.availability import list_booking_slots_flat



def list_dynamic_booking_slots(db: Session) -> list[BookingSlotSummary]:
    return list_booking_slots_flat(db)
