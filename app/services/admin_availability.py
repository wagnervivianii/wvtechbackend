from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.availability_day import AvailabilityDay
from app.models.availability_slot import AvailabilitySlot
from app.models.booking_request import BookingRequest
from app.models.client_workspace import ClientWorkspace
from app.models.client_workspace_meeting import ClientWorkspaceMeeting
from app.schemas.admin_availability import (
    AdminAvailabilityDayItem,
    AdminAvailabilityDayToggleRequest,
    AdminAvailabilityDayUpsertRequest,
    AdminAvailabilityListResponse,
    AdminAvailabilitySlotCreateRequest,
    AdminAvailabilitySlotItem,
    AdminAvailabilitySlotUpdateRequest,
    AdminBookingHistoryItem,
)
from app.services.availability import MONTH_LABELS, WEEKDAY_LABELS


TERMINAL_MEETING_STATUSES = {"completed", "cancelled", "no_show"}


def _extract_cancellation_reason(meeting_notes: str | None) -> str | None:
    if not meeting_notes:
        return None

    for chunk in meeting_notes.split("\n\n"):
        if chunk.startswith('[Motivo enviado ao cliente] '):
            return chunk.removeprefix('[Motivo enviado ao cliente] ').strip() or None

    return None


def _google_calendar_cancelled(meeting_notes: str | None) -> bool:
    if not meeting_notes:
        return False

    return '[Google Calendar] Evento cancelado automaticamente.' in meeting_notes


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


def _slot_starts_at(available_date: date, start_time: time) -> datetime:
    return datetime.combine(
        available_date,
        start_time,
        tzinfo=ZoneInfo(settings.app_timezone),
    )


def _slot_is_visible_in_active_agenda(
    available_date: date,
    slot: AvailabilitySlot,
    now_local: datetime,
) -> bool:
    return _slot_starts_at(available_date, slot.start_time) > now_local


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


def _serialize_history_item(
    booking: BookingRequest,
    workspace: ClientWorkspace | None,
) -> AdminBookingHistoryItem:
    start_text = booking.start_time.strftime("%H:%M") if booking.start_time else None
    end_text = booking.end_time.strftime("%H:%M") if booking.end_time else None

    if booking.booking_date and start_text and end_text:
        display_label = f"{booking.booking_date.strftime('%d/%m/%Y')} • {start_text} às {end_text}"
    elif booking.booking_date:
        display_label = booking.booking_date.strftime("%d/%m/%Y")
    else:
        display_label = f"Solicitação #{booking.id}"

    is_admin_cancelled = booking.status == 'cancelled_by_admin'

    return AdminBookingHistoryItem(
        id=booking.id,
        booking_date=booking.booking_date.isoformat() if booking.booking_date else None,
        start_time=start_text,
        end_time=end_text,
        display_label=display_label,
        status=booking.status,
        meeting_status=booking.meeting_status,
        name=booking.name,
        email=booking.email,
        phone=booking.phone,
        subject_summary=booking.subject_summary,
        meet_url=booking.meet_url,
        meet_event_id=booking.meet_event_id,
        meeting_notes=booking.meeting_notes,
        transcript_summary=booking.transcript_summary,
        has_transcript=bool(booking.transcript_text or booking.transcript_summary),
        created_at=booking.created_at.isoformat(),
        contact_confirmed_at=booking.contact_confirmed_at.isoformat() if booking.contact_confirmed_at else None,
        admin_reviewed_at=booking.admin_reviewed_at.isoformat() if booking.admin_reviewed_at else None,
        rejection_reason=booking.rejection_reason,
        cancellation_reason=_extract_cancellation_reason(booking.meeting_notes) if is_admin_cancelled else None,
        cancelled_at=booking.admin_reviewed_at.isoformat() if is_admin_cancelled and booking.admin_reviewed_at else None,
        google_calendar_cancelled=_google_calendar_cancelled(booking.meeting_notes) if is_admin_cancelled else False,
        can_schedule_again=booking.can_schedule_again,
        has_client_workspace=workspace is not None,
        client_workspace_status=workspace.workspace_status if workspace else None,
    )


def _booking_belongs_to_history(booking: BookingRequest, now_local: datetime) -> bool:
    if booking.status == 'rejected':
        return False

    if booking.status == 'cancelled_by_admin':
        return True

    if booking.meeting_status in TERMINAL_MEETING_STATUSES:
        return True

    if booking.booking_date is None:
        return False

    if booking.end_time is not None:
        booking_end = datetime.combine(
            booking.booking_date,
            booking.end_time,
            tzinfo=ZoneInfo(settings.app_timezone),
        )
        return booking_end <= now_local

    if booking.start_time is not None:
        booking_start = datetime.combine(
            booking.booking_date,
            booking.start_time,
            tzinfo=ZoneInfo(settings.app_timezone),
        )
        return booking_start <= now_local

    return booking.booking_date < now_local.date()


def _load_days_with_slots(db: Session) -> list[AdminAvailabilityDayItem]:
    now_local = _now_local()
    today = now_local.date()
    _, window_end = _window_limits()

    days = db.scalars(
        select(AvailabilityDay)
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
        .order_by(
            AvailabilitySlot.availability_day_id.asc(),
            AvailabilitySlot.start_time.asc(),
            AvailabilitySlot.end_time.asc(),
        )
    ).all()

    slots_by_day: dict[int, list[AvailabilitySlot]] = defaultdict(list)
    for slot in slots:
        slots_by_day[slot.availability_day_id].append(slot)

    items: list[AdminAvailabilityDayItem] = []
    for day in days:
        day_slots = slots_by_day.get(day.id, [])
        visible_slots = [
            slot
            for slot in day_slots
            if _slot_is_visible_in_active_agenda(day.available_date, slot, now_local)
        ]

        if day.available_date == today and day_slots and not visible_slots:
            continue

        items.append(_serialize_day(day=day, slots=visible_slots))

    return items


def _load_booking_history(db: Session) -> list[AdminBookingHistoryItem]:
    now_local = _now_local()
    bookings = db.scalars(
        select(BookingRequest).order_by(
            BookingRequest.booking_date.desc(),
            BookingRequest.start_time.desc(),
            BookingRequest.created_at.desc(),
        )
    ).all()

    if not bookings:
        return []

    booking_ids = [booking.id for booking in bookings]
    workspace_meetings = db.scalars(
        select(ClientWorkspaceMeeting).where(
            ClientWorkspaceMeeting.booking_request_id.in_(booking_ids)
        )
    ).all()

    workspace_ids = [item.workspace_id for item in workspace_meetings]
    workspaces: list[ClientWorkspace] = []
    if workspace_ids:
        workspaces = db.scalars(
            select(ClientWorkspace).where(ClientWorkspace.id.in_(workspace_ids))
        ).all()

    workspace_by_id = {workspace.id: workspace for workspace in workspaces}
    workspace_by_booking_id = {
        meeting.booking_request_id: workspace_by_id.get(meeting.workspace_id)
        for meeting in workspace_meetings
    }

    history_items: list[AdminBookingHistoryItem] = []
    for booking in bookings:
        if booking.status in {'approved', 'cancelled_by_admin'} or _booking_belongs_to_history(booking, now_local):
            history_items.append(
                _serialize_history_item(
                    booking,
                    workspace_by_booking_id.get(booking.id),
                )
            )

    return history_items


def _build_day_response(db: Session, day_id: int) -> AdminAvailabilityDayItem:
    now_local = _now_local()
    day = _get_day_or_404(db, day_id)
    slots = db.scalars(
        select(AvailabilitySlot)
        .where(AvailabilitySlot.availability_day_id == day.id)
        .order_by(AvailabilitySlot.start_time.asc(), AvailabilitySlot.end_time.asc())
    ).all()

    visible_slots = [
        slot
        for slot in slots
        if _slot_is_visible_in_active_agenda(day.available_date, slot, now_local)
    ]
    return _serialize_day(day=day, slots=visible_slots)


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
    return AdminAvailabilityListResponse(
        days=_load_days_with_slots(db),
        history=_load_booking_history(db),
    )


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

def delete_admin_slot(
    db: Session,
    *,
    slot_id: int,
) -> AdminAvailabilityDayItem:
    slot = _get_slot_or_404(db, slot_id)
    day_id = slot.availability_day_id

    db.delete(slot)
    db.commit()

    return _build_day_response(db, day_id)