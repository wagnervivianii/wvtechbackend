from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.availability_day import AvailabilityDay
from app.models.availability_slot import AvailabilitySlot
from app.models.booking_request import BookingRequest
from app.schemas.bookings import (
    BookingRequestCreate,
    BookingRequestCreated,
    BookingSlotSummary,
)


def create_booking_request(
    db: Session,
    payload: BookingRequestCreate,
) -> BookingRequestCreated:
    try:
        availability_slot_id = int(payload.slot_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Horário selecionado inválido",
        ) from exc

    slot = db.scalar(
        select(AvailabilitySlot)
        .where(AvailabilitySlot.id == availability_slot_id)
        .where(AvailabilitySlot.is_active.is_(True))
    )

    if slot is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Horário selecionado não encontrado",
        )

    day = db.scalar(
        select(AvailabilityDay)
        .where(AvailabilityDay.id == slot.availability_day_id)
        .where(AvailabilityDay.is_active.is_(True))
    )

    if day is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dia selecionado não está mais disponível",
        )

    now = datetime.now(ZoneInfo(settings.app_timezone))
    first_day_of_current_month = now.date().replace(day=1)
    if first_day_of_current_month.month == 12:
        next_month = first_day_of_current_month.replace(year=first_day_of_current_month.year + 1, month=1)
    else:
        next_month = first_day_of_current_month.replace(month=first_day_of_current_month.month + 1)

    if next_month.month == 12:
        month_after_next = next_month.replace(year=next_month.year + 1, month=1)
    else:
        month_after_next = next_month.replace(month=next_month.month + 1)

    if not (first_day_of_current_month <= day.available_date < month_after_next):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Horário fora da janela atual de agendamento",
        )

    slot_starts_at = datetime.combine(
        day.available_date,
        slot.start_time,
        tzinfo=ZoneInfo(settings.app_timezone),
    )
    if slot_starts_at <= now:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Horário selecionado já expirou",
        )

    booking_request = BookingRequest(
        slot_id=str(slot.id),
        availability_slot_id=slot.id,
        booking_date=day.available_date,
        start_time=slot.start_time,
        end_time=slot.end_time,
        name=payload.name,
        email=payload.email,
        phone=payload.phone,
        subject_summary=payload.subject_summary,
        status="pending_contact_confirmation",
        meeting_status="scheduled",
    )

    db.add(booking_request)
    db.commit()
    db.refresh(booking_request)

    start_text = slot.start_time.strftime("%H:%M")
    end_text = slot.end_time.strftime("%H:%M")

    return BookingRequestCreated(
        status=booking_request.status,
        message="Solicitação recebida com sucesso",
        slot_id=booking_request.slot_id,
        booking_date=day.available_date,
        name=booking_request.name,
        email=booking_request.email,
        phone=booking_request.phone,
        subject_summary=booking_request.subject_summary,
        slot=BookingSlotSummary(
            id=str(slot.id),
            availability_slot_id=slot.id,
            date=day.available_date.isoformat(),
            start_time=start_text,
            end_time=end_text,
            label=f"{day.available_date.strftime('%d/%m/%Y')} • {start_text} às {end_text}",
        ),
    )