from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.availability_day import AvailabilityDay
from app.models.availability_slot import AvailabilitySlot
from app.schemas.availability import (
    AvailabilityCalendarDay,
    AvailabilityCalendarMonth,
    AvailabilityCalendarResponse,
    AvailabilitySlotListResponse,
)
from app.schemas.bookings import BookingSlotSummary

WEEKDAY_LABELS = [
    "segunda",
    "terça",
    "quarta",
    "quinta",
    "sexta",
    "sábado",
    "domingo",
]

MONTH_LABELS = [
    "janeiro",
    "fevereiro",
    "março",
    "abril",
    "maio",
    "junho",
    "julho",
    "agosto",
    "setembro",
    "outubro",
    "novembro",
    "dezembro",
]


def _window_limits() -> tuple[date, date]:
    now = datetime.now(ZoneInfo(settings.app_timezone))
    window_start = now.date().replace(day=1)

    if window_start.month == 12:
        next_month = date(window_start.year + 1, 1, 1)
    else:
        next_month = date(window_start.year, window_start.month + 1, 1)

    if next_month.month == 12:
        month_after_next = date(next_month.year + 1, 1, 1)
    else:
        month_after_next = date(next_month.year, next_month.month + 1, 1)

    window_end = month_after_next - timedelta(days=1)
    return window_start, window_end


def _active_days_query() -> Select[tuple[AvailabilityDay]]:
    window_start, window_end = _window_limits()
    return (
        select(AvailabilityDay)
        .where(AvailabilityDay.is_active.is_(True))
        .where(AvailabilityDay.available_date >= window_start)
        .where(AvailabilityDay.available_date <= window_end)
        .order_by(AvailabilityDay.available_date.asc())
    )


def _slot_summary(slot: AvailabilitySlot, available_date: date) -> BookingSlotSummary:
    start_text = slot.start_time.strftime("%H:%M")
    end_text = slot.end_time.strftime("%H:%M")
    date_text = available_date.isoformat()
    label = f"{available_date.strftime('%d/%m/%Y')} • {start_text} às {end_text}"

    return BookingSlotSummary(
        id=str(slot.id),
        availability_slot_id=slot.id,
        date=date_text,
        start_time=start_text,
        end_time=end_text,
        label=label,
    )


def list_availability_calendar(db: Session) -> AvailabilityCalendarResponse:
    days = db.scalars(_active_days_query()).all()

    grouped: dict[tuple[int, int], list[AvailabilityCalendarDay]] = defaultdict(list)
    for day in days:
        grouped[(day.available_date.year, day.available_date.month)].append(
            AvailabilityCalendarDay(
                date=day.available_date.isoformat(),
                weekday_label=WEEKDAY_LABELS[day.available_date.weekday()],
                day_label=day.available_date.strftime("%d"),
                month_label=MONTH_LABELS[day.available_date.month - 1],
            )
        )

    months: list[AvailabilityCalendarMonth] = []
    for year_month in sorted(grouped.keys()):
        year, month = year_month
        months.append(
            AvailabilityCalendarMonth(
                year=year,
                month=month,
                month_label=f"{MONTH_LABELS[month - 1].capitalize()} de {year}",
                days=grouped[year_month],
            )
        )

    return AvailabilityCalendarResponse(months=months)


def list_availability_slots(db: Session, selected_date: date) -> AvailabilitySlotListResponse:
    window_start, window_end = _window_limits()
    if selected_date < window_start or selected_date > window_end:
        return AvailabilitySlotListResponse(date=selected_date.isoformat(), slots=[])

    day = db.scalar(
        select(AvailabilityDay)
        .where(AvailabilityDay.is_active.is_(True))
        .where(AvailabilityDay.available_date == selected_date)
    )

    if day is None:
        return AvailabilitySlotListResponse(date=selected_date.isoformat(), slots=[])

    slots = db.scalars(
        select(AvailabilitySlot)
        .where(AvailabilitySlot.availability_day_id == day.id)
        .where(AvailabilitySlot.is_active.is_(True))
        .order_by(AvailabilitySlot.start_time.asc())
    ).all()

    return AvailabilitySlotListResponse(
        date=selected_date.isoformat(),
        slots=[_slot_summary(slot=slot, available_date=day.available_date) for slot in slots],
    )


def list_booking_slots_flat(db: Session) -> list[BookingSlotSummary]:
    days = db.scalars(_active_days_query()).all()
    if not days:
        return []

    day_map = {day.id: day for day in days}
    slots = db.scalars(
        select(AvailabilitySlot)
        .where(AvailabilitySlot.availability_day_id.in_(day_map.keys()))
        .where(AvailabilitySlot.is_active.is_(True))
        .order_by(AvailabilitySlot.availability_day_id.asc(), AvailabilitySlot.start_time.asc())
    ).all()

    summaries: list[BookingSlotSummary] = []
    for slot in slots:
        day = day_map.get(slot.availability_day_id)
        if day is None:
            continue
        summaries.append(_slot_summary(slot=slot, available_date=day.available_date))

    return summaries
