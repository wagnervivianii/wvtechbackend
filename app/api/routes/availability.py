from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.availability import AvailabilityCalendarResponse, AvailabilitySlotListResponse
from app.services.availability import list_availability_calendar, list_availability_slots

router = APIRouter(prefix="/availability", tags=["availability"])


@router.get("/calendar", response_model=AvailabilityCalendarResponse)
def get_availability_calendar(
    db: Session = Depends(get_db),
) -> AvailabilityCalendarResponse:
    return list_availability_calendar(db=db)


@router.get("/slots", response_model=AvailabilitySlotListResponse)
def get_availability_slots(
    selected_date: date = Query(..., alias="date", description="Data consultada no formato YYYY-MM-DD"),
    db: Session = Depends(get_db),
) -> AvailabilitySlotListResponse:
    return list_availability_slots(db=db, selected_date=selected_date)
