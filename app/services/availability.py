from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.availability_day import AvailabilityDay
from app.models.availability_slot import AvailabilitySlot
from app.models.booking_request import BookingRequest
from app.schemas.availability import (
    AvailabilityCalendarDay,
    AvailabilityCalendarMonth,
    AvailabilityCalendarResponse,
    AvailabilitySlotListResponse,
)
from app.schemas.bookings import BookingSlotSummary
from app.services.booking_request_status import BLOCKING_BOOKING_REQUEST_STATUSES

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


def _now_local() -> datetime:
    return datetime.now(ZoneInfo(settings.app_timezone))


def _window_limits() -> tuple[date, date]:
    now = _now_local()
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


def _slot_starts_at(available_date: date, start_time) -> datetime:
    return datetime.combine(
        available_date,
        start_time,
        tzinfo=ZoneInfo(settings.app_timezone),
    )


def _slot_is_future(available_date: date, slot: AvailabilitySlot, now_local: datetime) -> bool:
    return _slot_starts_at(available_date, slot.start_time) > now_local


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


def _load_blocked_slot_ids(
    db: Session,
    *,
    slot_ids: list[int],
) -> set[int]:
    if not slot_ids:
        return set()

    blocked_ids = db.scalars(
        select(BookingRequest.availability_slot_id)
        .where(BookingRequest.availability_slot_id.in_(slot_ids))
        .where(BookingRequest.status.in_(BLOCKING_BOOKING_REQUEST_STATUSES))
        .distinct()
    ).all()

    return {slot_id for slot_id in blocked_ids if slot_id is not None}


def _load_public_days_with_slots(
    db: Session,
) -> list[tuple[AvailabilityDay, list[AvailabilitySlot]]]:
    now_local = _now_local()
    today = now_local.date()
    _, window_end = _window_limits()

    days = db.scalars(
        select(AvailabilityDay)
        .where(AvailabilityDay.is_active.is_(True))
        .where(AvailabilityDay.available_date >= today)
        .where(AvailabilityDay.available_date <= window_end)
        .order_by(AvailabilityDay.available_date.asc())
    ).all()

    if not days:
        return []

    day_ids = [day.id for day in days]
    slots = db.scalars(
        select(AvailabilitySlot)
        .where(AvailabilitySlot.availability_day_id.in_(day_ids))
        .where(AvailabilitySlot.is_active.is_(True))
        .order_by(
            AvailabilitySlot.availability_day_id.asc(),
            AvailabilitySlot.start_time.asc(),
            AvailabilitySlot.end_time.asc(),
        )
    ).all()

    blocked_slot_ids = _load_blocked_slot_ids(
        db,
        slot_ids=[slot.id for slot in slots],
    )

    slots_by_day: dict[int, list[AvailabilitySlot]] = defaultdict(list)
    for slot in slots:
        if slot.id in blocked_slot_ids:
            continue
        slots_by_day[slot.availability_day_id].append(slot)

    visible_days: list[tuple[AvailabilityDay, list[AvailabilitySlot]]] = []
    for day in days:
        visible_slots = [
            slot
            for slot in slots_by_day.get(day.id, [])
            if _slot_is_future(day.available_date, slot, now_local)
        ]
        if visible_slots:
            visible_days.append((day, visible_slots))

    return visible_days


def list_availability_calendar(db: Session) -> AvailabilityCalendarResponse:
    days_with_slots = _load_public_days_with_slots(db)

    grouped: dict[tuple[int, int], list[AvailabilityCalendarDay]] = defaultdict(list)
    for day, visible_slots in days_with_slots:
        if not visible_slots:
            continue

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
    now_local = _now_local()
    today = now_local.date()
    _, window_end = _window_limits()

    if selected_date < today or selected_date > window_end:
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

    blocked_slot_ids = _load_blocked_slot_ids(
        db,
        slot_ids=[slot.id for slot in slots],
    )

    visible_slots = [
        slot
        for slot in slots
        if slot.id not in blocked_slot_ids
        and _slot_is_future(day.available_date, slot, now_local)
    ]

    return AvailabilitySlotListResponse(
        date=selected_date.isoformat(),
        slots=[_slot_summary(slot=slot, available_date=day.available_date) for slot in visible_slots],
    )


def list_booking_slots_flat(db: Session) -> list[BookingSlotSummary]:
    days_with_slots = _load_public_days_with_slots(db)

    summaries: list[BookingSlotSummary] = []
    for day, visible_slots in days_with_slots:
        for slot in visible_slots:
            summaries.append(_slot_summary(slot=slot, available_date=day.available_date))

    return summaries