from __future__ import annotations

from datetime import datetime, timedelta
import hashlib
import secrets
from zoneinfo import ZoneInfo

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.booking_request import BookingRequest
from app.models.booking_request_confirmation import BookingRequestConfirmation
from app.schemas.bookings import BookingEmailConfirmationResponse


PENDING_CONFIRMATION_STATUSES = {"pending", "replaced"}


def _now_local() -> datetime:
    return datetime.now(ZoneInfo(settings.app_timezone))


def _hash_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def _build_confirmation_preview_path(raw_token: str) -> str:
    path_prefix = settings.booking_confirmation_path_prefix.rstrip("/")
    return f"{path_prefix}/{raw_token}"


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
        if item.confirmation_status == "pending":
            item.confirmation_status = "replaced"
            db.add(item)

    confirmation = BookingRequestConfirmation(
        booking_request_id=booking.id,
        confirmation_token_hash=token_hash,
        confirmation_status="pending",
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
            detail="Token de confirmação não encontrado.",
        )

    booking = db.get(BookingRequest, confirmation.booking_request_id)
    if booking is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Solicitação vinculada ao token não foi encontrada.",
        )

    now_local = _now_local()

    if confirmation.confirmation_status == "confirmed" and booking.contact_confirmed_at is not None:
        return BookingEmailConfirmationResponse(
            booking_id=booking.id,
            status=booking.status,
            message="Este email já foi confirmado anteriormente.",
            confirmed_at=booking.contact_confirmed_at.isoformat(),
        )

    if confirmation.expires_at is not None and confirmation.expires_at < now_local:
        confirmation.confirmation_status = "expired"
        db.add(confirmation)
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Este link de confirmação expirou.",
        )

    if confirmation.confirmation_status != "pending":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Este token de confirmação não está mais ativo.",
        )

    confirmation.confirmation_status = "confirmed"
    confirmation.confirmed_at = now_local

    booking.contact_confirmed_at = now_local
    booking.status = "email_confirmed_pending_admin_review"

    db.add(confirmation)
    db.add(booking)
    db.commit()
    db.refresh(booking)

    return BookingEmailConfirmationResponse(
        booking_id=booking.id,
        status=booking.status,
        message=(
            "Email confirmado com sucesso. Sua solicitação agora aguarda análise administrativa."
        ),
        confirmed_at=booking.contact_confirmed_at.isoformat(),
    )


def build_confirmation_preview_path(raw_token: str) -> str:
    return _build_confirmation_preview_path(raw_token)