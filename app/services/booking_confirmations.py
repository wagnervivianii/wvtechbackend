from __future__ import annotations

from datetime import datetime, timedelta
import hashlib
import secrets
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.booking_request import BookingRequest
from app.models.booking_request_confirmation import BookingRequestConfirmation
from app.schemas.bookings import BookingEmailConfirmationResponse


PENDING_CONFIRMATION_STATUSES = {'pending', 'replaced'}
MAX_TRACKED_CONFIRMATION_ACCESSES = 2
CONSUMED_CONFIRMATION_DETAIL = 'Link de confirmação já consumido.'


def _now_local() -> datetime:
    return datetime.now(ZoneInfo(settings.app_timezone))


def _hash_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode('utf-8')).hexdigest()


def _build_confirmation_preview_path(raw_token: str) -> str:
    path_prefix = settings.booking_confirmation_path_prefix.rstrip('/')
    return f'{path_prefix}/{raw_token}'


def build_confirmation_result_url(*, result_status: str, booking_id: int | None = None) -> str:
    base_url = settings.public_app_base_url.rstrip('/')
    path = settings.booking_confirmation_result_path_prefix.rstrip('/')
    params: dict[str, str] = {'status': result_status}
    if booking_id is not None:
        params['booking_id'] = str(booking_id)
    return f'{base_url}{path}?{urlencode(params)}'


def build_confirmation_action_url(raw_token: str) -> str:
    base_url = settings.booking_confirmation_action_base_url.rstrip('/')
    return f'{base_url}/bookings/confirm/{raw_token}'


def _increment_access_count(
    db: Session,
    *,
    confirmation: BookingRequestConfirmation,
) -> None:
    current_count = confirmation.access_count or 0
    if current_count >= MAX_TRACKED_CONFIRMATION_ACCESSES:
        return

    confirmation.access_count = current_count + 1
    db.add(confirmation)


def create_booking_confirmation(
    db: Session,
    *,
    booking: BookingRequest,
    ttl_hours: int | None = None,
) -> str:
    raw_token = secrets.token_urlsafe(32)
    token_hash = _hash_token(raw_token)
    now_local = _now_local()
    effective_ttl = ttl_hours or settings.booking_confirmation_ttl_hours

    previous_confirmations = db.scalars(
        select(BookingRequestConfirmation).where(
            BookingRequestConfirmation.booking_request_id == booking.id
        )
    ).all()
    for item in previous_confirmations:
        if item.confirmation_status == 'pending':
            item.confirmation_status = 'replaced'
            db.add(item)

    confirmation = BookingRequestConfirmation(
        booking_request_id=booking.id,
        confirmation_token_hash=token_hash,
        confirmation_status='pending',
        access_count=0,
        expires_at=now_local + timedelta(hours=effective_ttl),
    )
    db.add(confirmation)
    db.flush()

    return raw_token


def confirm_booking_request_email(
    db: Session,
    *,
    raw_token: str,
) -> BookingEmailConfirmationResponse:
    token_hash = _hash_token(raw_token)
    confirmation = db.scalar(
        select(BookingRequestConfirmation).where(
            BookingRequestConfirmation.confirmation_token_hash == token_hash
        )
    )

    if confirmation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail='Token de confirmação não encontrado.',
        )

    if (
        confirmation.confirmation_status == 'confirmed'
        and (confirmation.access_count or 0) >= MAX_TRACKED_CONFIRMATION_ACCESSES
    ):
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail=CONSUMED_CONFIRMATION_DETAIL,
        )

    booking = db.get(BookingRequest, confirmation.booking_request_id)
    if booking is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail='Solicitação vinculada ao token não foi encontrada.',
        )

    now_local = _now_local()

    if confirmation.confirmation_status == 'confirmed' and booking.contact_confirmed_at is not None:
        _increment_access_count(db, confirmation=confirmation)
        db.commit()
        return BookingEmailConfirmationResponse(
            booking_id=booking.id,
            status=booking.status,
            result_status='already-confirmed',
            message='Este email já foi confirmado anteriormente.',
            confirmed_at=booking.contact_confirmed_at.isoformat(),
        )

    if confirmation.expires_at is not None and confirmation.expires_at < now_local:
        confirmation.confirmation_status = 'expired'
        db.add(confirmation)
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail='Este link de confirmação expirou.',
        )

    if confirmation.confirmation_status != 'pending':
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail='Este token de confirmação não está mais ativo.',
        )

    _increment_access_count(db, confirmation=confirmation)
    confirmation.confirmation_status = 'confirmed'
    confirmation.confirmed_at = now_local

    booking.contact_confirmed_at = now_local
    booking.status = 'email_confirmed_pending_admin_review'

    db.add(confirmation)
    db.add(booking)
    db.commit()
    db.refresh(booking)

    return BookingEmailConfirmationResponse(
        booking_id=booking.id,
        status=booking.status,
        result_status='success',
        message=(
            'Email confirmado com sucesso. Sua solicitação agora aguarda análise administrativa.'
        ),
        confirmed_at=booking.contact_confirmed_at.isoformat(),
    )


def build_confirmation_preview_path(raw_token: str) -> str:
    return _build_confirmation_preview_path(raw_token)