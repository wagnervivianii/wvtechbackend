from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta, time
from zoneinfo import ZoneInfo

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.availability_day import AvailabilityDay
from app.models.availability_slot import AvailabilitySlot
from app.schemas.admin_availability import (
    AdminAvailabilityDayItem,
    AdminAvailabilityDayToggleRequest,
    AdminAvailabilityDayUpsertRequest,
    AdminAvailabilityListResponse,
    AdminAvailabilitySlotCreateRequest,
    AdminAvailabilitySlotItem,
    AdminAvailabilitySlotUpdateRequest,
)
from app.services.availability import MONTH_LABELS, WEEKDAY_LABELS


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


def _ensure_date_inside_window(available_date: date) -> None:
    window_start, window_end = _window_limits()
    if available_date < window_start or available_date > window_end:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "A gestão de disponibilidade aceita apenas datas do mês atual "
                "e do próximo mês."
            ),
        )


def _get_day_or_404(db: Session, day_id: int) -> AvailabilityDay:
    day = db.get(AvailabilityDay, day_id)
    if day is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dia de disponibilidade não encontrado.",
        )
    return day


def _get_slot_or_404(db: Session, slot_id: int) -> AvailabilitySlot:
    slot = db.get(AvailabilitySlot, slot_id)
    if slot is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Horário de disponibilidade não encontrado.",
        )
    return slot


def _serialize_slot(slot: AvailabilitySlot) -> AdminAvailabilitySlotItem:
    start_text = slot.start_time.strftime("%H:%M")
    end_text = slot.end_time.strftime("%H:%M")
    return AdminAvailabilitySlotItem(
        id=slot.id,
        start_time=start_text,
        end_time=end_text,
        timezone_name=slot.timezone_name,
        is_active=slot.is_active,
        label=f"{start_text} às {end_text}",
    )


def _serialize_day(
    day: AvailabilityDay,
    slots: list[AvailabilitySlot],
) -> AdminAvailabilityDayItem:
    slot_items = [_serialize_slot(slot) for slot in slots]
    weekday_label = WEEKDAY_LABELS[day.available_date.weekday()]
    day_label = day.available_date.strftime("%d")
    month_label = MONTH_LABELS[day.available_date.month - 1]

    return AdminAvailabilityDayItem(
        id=day.id,
        date=day.available_date.isoformat(),
        weekday_label=weekday_label,
        day_label=day_label,
        month_label=month_label,
        display_label=(
            f"{weekday_label.capitalize()} • "
            f"{day.available_date.strftime('%d/%m/%Y')}"
        ),
        is_active=day.is_active,
        has_active_slots=any(slot.is_active for slot in slots),
        notes=day.notes,
        slots=slot_items,
    )


def _load_days_with_slots(db: Session) -> list[AdminAvailabilityDayItem]:
    window_start, window_end = _window_limits()
    days = db.scalars(
        select(AvailabilityDay)
        .where(AvailabilityDay.available_date >= window_start)
        .where(AvailabilityDay.available_date <= window_end)
        .order_by(AvailabilityDay.available_date.asc())
    ).all()

    if not days:
        return []

    day_ids = [day.id for day in days]
    slots = db.scalars(
        select(AvailabilitySlot)
        .where(AvailabilitySlot.availability_day_id.in_(day_ids))
        .order_by(
            AvailabilitySlot.availability_day_id.asc(),
            AvailabilitySlot.start_time.asc(),
            AvailabilitySlot.end_time.asc(),
        )
    ).all()

    slots_by_day: dict[int, list[AvailabilitySlot]] = defaultdict(list)
    for slot in slots:
        slots_by_day[slot.availability_day_id].append(slot)

    return [_serialize_day(day=day, slots=slots_by_day.get(day.id, [])) for day in days]


def _build_day_response(db: Session, day_id: int) -> AdminAvailabilityDayItem:
    day = _get_day_or_404(db, day_id)
    slots = db.scalars(
        select(AvailabilitySlot)
        .where(AvailabilitySlot.availability_day_id == day.id)
        .order_by(AvailabilitySlot.start_time.asc(), AvailabilitySlot.end_time.asc())
    ).all()
    return _serialize_day(day=day, slots=slots)


def _ensure_valid_time_range(start_time: time, end_time: time) -> None:
    if start_time >= end_time:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A hora final deve ser maior que a hora inicial.",
        )


def _ensure_slot_without_overlap(
    db: Session,
    *,
    day_id: int,
    start_time: time,
    end_time: time,
    exclude_slot_id: int | None = None,
) -> None:
    existing_slots = db.scalars(
        select(AvailabilitySlot)
        .where(AvailabilitySlot.availability_day_id == day_id)
        .order_by(AvailabilitySlot.start_time.asc())
    ).all()

    for slot in existing_slots:
        if exclude_slot_id is not None and slot.id == exclude_slot_id:
            continue

        if start_time < slot.end_time and end_time > slot.start_time:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Já existe um horário cadastrado que conflita com o intervalo "
                    "informado para este dia."
                ),
            )


def list_admin_availability(db: Session) -> AdminAvailabilityListResponse:
    return AdminAvailabilityListResponse(days=_load_days_with_slots(db))


def upsert_admin_day(
    db: Session,
    payload: AdminAvailabilityDayUpsertRequest,
) -> AdminAvailabilityDayItem:
    _ensure_date_inside_window(payload.date)

    day = db.scalar(
        select(AvailabilityDay).where(AvailabilityDay.available_date == payload.date)
    )

    if day is None:
        day = AvailabilityDay(
            available_date=payload.date,
            is_active=payload.is_active,
        )
        db.add(day)
        db.commit()
        db.refresh(day)
        return _build_day_response(db, day.id)

    day.is_active = payload.is_active
    db.commit()
    db.refresh(day)
    return _build_day_response(db, day.id)


def toggle_admin_day(
    db: Session,
    *,
    day_id: int,
    payload: AdminAvailabilityDayToggleRequest,
) -> AdminAvailabilityDayItem:
    day = _get_day_or_404(db, day_id)
    day.is_active = payload.is_active
    db.commit()
    db.refresh(day)
    return _build_day_response(db, day.id)


def create_admin_slot(
    db: Session,
    *,
    day_id: int,
    payload: AdminAvailabilitySlotCreateRequest,
) -> AdminAvailabilityDayItem:
    day = _get_day_or_404(db, day_id)
    _ensure_date_inside_window(day.available_date)
    _ensure_valid_time_range(payload.start_time, payload.end_time)
    _ensure_slot_without_overlap(
        db,
        day_id=day.id,
        start_time=payload.start_time,
        end_time=payload.end_time,
    )

    slot = AvailabilitySlot(
        availability_day_id=day.id,
        start_time=payload.start_time,
        end_time=payload.end_time,
        timezone_name=payload.timezone_name,
        is_active=payload.is_active,
    )
    db.add(slot)
    db.commit()
    return _build_day_response(db, day.id)


def update_admin_slot(
    db: Session,
    *,
    slot_id: int,
    payload: AdminAvailabilitySlotUpdateRequest,
) -> AdminAvailabilityDayItem:
    slot = _get_slot_or_404(db, slot_id)
    day = _get_day_or_404(db, slot.availability_day_id)
    _ensure_date_inside_window(day.available_date)
    _ensure_valid_time_range(payload.start_time, payload.end_time)
    _ensure_slot_without_overlap(
        db,
        day_id=day.id,
        start_time=payload.start_time,
        end_time=payload.end_time,
        exclude_slot_id=slot.id,
    )

    slot.start_time = payload.start_time
    slot.end_time = payload.end_time
    slot.timezone_name = payload.timezone_name
    slot.is_active = payload.is_active
    db.commit()
    return _build_day_response(db, day.id)


def delete_admin_slot(db: Session, *, slot_id: int) -> AdminAvailabilityDayItem:
    slot = _get_slot_or_404(db, slot_id)
    day_id = slot.availability_day_id
    db.delete(slot)
    db.commit()
    return _build_day_response(db, day_id)