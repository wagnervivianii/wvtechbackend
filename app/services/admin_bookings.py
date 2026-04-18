from datetime import datetime
import logging
from zoneinfo import ZoneInfo

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.booking_request import BookingRequest
from app.models.client_workspace_invite import ClientWorkspaceInvite
from app.schemas.admin_bookings import (
    AdminBookingApprovalRequest,
    AdminBookingDecisionResponse,
    AdminBookingPendingReviewItem,
    AdminBookingPendingReviewListResponse,
    AdminBookingRebookingPermissionRequest,
    AdminBookingRebookingPermissionResponse,
    AdminBookingRejectionRequest,
)
from app.schemas.admin_client_workspaces import AdminClientWorkspaceProvisionRequest
from app.services.admin_client_workspaces import (
    get_client_workspace_by_booking,
    provision_client_workspace_for_booking,
)
from app.services.booking_request_status import REOPENED_BOOKING_REQUEST_STATUSES
from app.services.email_notifications import send_email
from app.services.email_templates import (
    build_booking_approved_email,
    build_booking_rejected_email,
    build_client_setup_url,
)


logger = logging.getLogger(__name__)

TERMINAL_MEETING_STATUSES = {'completed', 'cancelled', 'no_show'}
PENDING_ADMIN_REVIEW_STATUS = 'email_confirmed_pending_admin_review'


def _now_local() -> datetime:
    return datetime.now(ZoneInfo(settings.app_timezone))


def _booking_has_already_happened(booking: BookingRequest) -> bool:
    if booking.status in REOPENED_BOOKING_REQUEST_STATUSES:
        return True

    if booking.meeting_status in TERMINAL_MEETING_STATUSES:
        return True

    if booking.booking_date is None:
        return False

    now_local = _now_local()

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


def _get_booking_or_404(db: Session, booking_id: int) -> BookingRequest:
    booking = db.get(BookingRequest, booking_id)
    if booking is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail='Solicitação de reunião não encontrada.',
        )
    return booking


def _ensure_booking_waiting_admin_review(booking: BookingRequest) -> None:
    if booking.status != PENDING_ADMIN_REVIEW_STATUS:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail='Esta solicitação não está aguardando análise administrativa.',
        )


def _build_display_label(booking: BookingRequest) -> str:
    start_text = booking.start_time.strftime('%H:%M') if booking.start_time else None
    end_text = booking.end_time.strftime('%H:%M') if booking.end_time else None

    if booking.booking_date and start_text and end_text:
        return f"{booking.booking_date.strftime('%d/%m/%Y')} • {start_text} às {end_text}"
    if booking.booking_date:
        return booking.booking_date.strftime('%d/%m/%Y')
    return f'Solicitação #{booking.id}'


def _serialize_pending_review_item(booking: BookingRequest) -> AdminBookingPendingReviewItem:
    return AdminBookingPendingReviewItem(
        id=booking.id,
        booking_date=booking.booking_date.isoformat() if booking.booking_date else None,
        start_time=booking.start_time.strftime('%H:%M') if booking.start_time else None,
        end_time=booking.end_time.strftime('%H:%M') if booking.end_time else None,
        display_label=_build_display_label(booking),
        status=booking.status,
        meeting_status=booking.meeting_status,
        name=booking.name,
        email=booking.email,
        phone=booking.phone,
        subject_summary=booking.subject_summary,
        created_at=booking.created_at.isoformat(),
        contact_confirmed_at=(
            booking.contact_confirmed_at.isoformat() if booking.contact_confirmed_at else booking.created_at.isoformat()
        ),
    )


def _load_workspace_detail_or_none(db: Session, booking_id: int):
    try:
        return get_client_workspace_by_booking(db=db, booking_id=booking_id)
    except HTTPException as exc:
        if exc.status_code == status.HTTP_404_NOT_FOUND:
            return None
        raise


def _serialize_decision_response(
    db: Session,
    booking: BookingRequest,
) -> AdminBookingDecisionResponse:
    return AdminBookingDecisionResponse(
        id=booking.id,
        status=booking.status,
        meeting_status=booking.meeting_status,
        name=booking.name,
        email=booking.email,
        phone=booking.phone,
        subject_summary=booking.subject_summary,
        booking_date=booking.booking_date.isoformat() if booking.booking_date else None,
        start_time=booking.start_time.strftime('%H:%M') if booking.start_time else None,
        end_time=booking.end_time.strftime('%H:%M') if booking.end_time else None,
        meet_url=booking.meet_url,
        meet_event_id=booking.meet_event_id,
        meeting_notes=booking.meeting_notes,
        contact_confirmed_at=(
            booking.contact_confirmed_at.isoformat() if booking.contact_confirmed_at else None
        ),
        admin_reviewed_at=(
            booking.admin_reviewed_at.isoformat() if booking.admin_reviewed_at else None
        ),
        rejection_reason=booking.rejection_reason,
        can_schedule_again=booking.can_schedule_again,
        client_workspace=_load_workspace_detail_or_none(db, booking.id),
    )


def _mark_initial_invite_as_sent(db: Session, invite_id: int | None) -> None:
    if invite_id is None:
        return

    invite = db.get(ClientWorkspaceInvite, invite_id)
    if invite is None:
        return

    invite.sent_at = _now_local()
    db.add(invite)
    db.commit()


def _send_booking_approved_email_best_effort(
    db: Session,
    *,
    booking: BookingRequest,
    client_setup_url: str | None,
    invite_id_to_mark: int | None,
) -> None:
    try:
        email_content = build_booking_approved_email(
            booking=booking,
            client_setup_url=client_setup_url,
        )
        send_email(to_email=booking.email, content=email_content)
        _mark_initial_invite_as_sent(db, invite_id_to_mark)
    except Exception:
        logger.exception(
            'Falha ao enviar email de aprovação para booking_id=%s',
            booking.id,
        )


def _send_booking_rejected_email_best_effort(*, booking: BookingRequest) -> None:
    try:
        email_content = build_booking_rejected_email(booking=booking)
        send_email(to_email=booking.email, content=email_content)
    except Exception:
        logger.exception(
            'Falha ao enviar email de rejeição para booking_id=%s',
            booking.id,
        )


def list_pending_admin_review(db: Session) -> AdminBookingPendingReviewListResponse:
    bookings = db.scalars(
        select(BookingRequest)
        .where(BookingRequest.status == PENDING_ADMIN_REVIEW_STATUS)
        .order_by(
            BookingRequest.contact_confirmed_at.desc(),
            BookingRequest.created_at.desc(),
            BookingRequest.id.desc(),
        )
    ).all()

    return AdminBookingPendingReviewListResponse(
        items=[_serialize_pending_review_item(item) for item in bookings]
    )


def approve_booking_request(
    db: Session,
    *,
    booking_id: int,
    payload: AdminBookingApprovalRequest,
) -> AdminBookingDecisionResponse:
    booking = _get_booking_or_404(db, booking_id)
    _ensure_booking_waiting_admin_review(booking)

    now_local = _now_local()
    booking.status = 'approved'
    booking.admin_reviewed_at = now_local
    booking.rejection_reason = None

    if payload.meet_url is not None:
        booking.meet_url = payload.meet_url
    if payload.meet_event_id is not None:
        booking.meet_event_id = payload.meet_event_id
    if payload.meeting_notes is not None:
        booking.meeting_notes = payload.meeting_notes

    db.add(booking)
    db.commit()
    db.refresh(booking)

    workspace_detail = None
    invite_id_to_mark: int | None = None
    client_setup_url: str | None = None

    if payload.create_client_workspace:
        workspace_detail = provision_client_workspace_for_booking(
            db=db,
            booking_id=booking.id,
            payload=AdminClientWorkspaceProvisionRequest(
                create_invite=payload.create_workspace_invite,
                invite_ttl_hours=payload.invite_ttl_hours,
                portal_notes=payload.portal_notes,
            ),
        )
        booking = _get_booking_or_404(db, booking_id)
        client_setup_url = build_client_setup_url(workspace_detail.setup_path)
        if workspace_detail.invites and workspace_detail.setup_token:
            invite_id_to_mark = workspace_detail.invites[0].id

    _send_booking_approved_email_best_effort(
        db,
        booking=booking,
        client_setup_url=client_setup_url,
        invite_id_to_mark=invite_id_to_mark,
    )

    return _serialize_decision_response(db, booking)


def reject_booking_request(
    db: Session,
    *,
    booking_id: int,
    payload: AdminBookingRejectionRequest,
) -> AdminBookingDecisionResponse:
    booking = _get_booking_or_404(db, booking_id)
    _ensure_booking_waiting_admin_review(booking)

    booking.status = 'rejected'
    booking.meeting_status = 'cancelled'
    booking.admin_reviewed_at = _now_local()
    booking.rejection_reason = payload.rejection_reason

    if payload.meeting_notes is not None:
        booking.meeting_notes = payload.meeting_notes

    db.add(booking)
    db.commit()
    db.refresh(booking)

    _send_booking_rejected_email_best_effort(booking=booking)

    return _serialize_decision_response(db, booking)


def update_rebooking_permission(
    db: Session,
    *,
    booking_id: int,
    payload: AdminBookingRebookingPermissionRequest,
) -> AdminBookingRebookingPermissionResponse:
    booking = db.get(BookingRequest, booking_id)
    if booking is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail='Solicitação de reunião não encontrada.',
        )

    if payload.can_schedule_again and not _booking_has_already_happened(booking):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                'A liberação de novo agendamento só pode acontecer depois que a reunião '
                'anterior já tiver ocorrido ou sido encerrada manualmente.'
            ),
        )

    booking.can_schedule_again = payload.can_schedule_again
    db.add(booking)
    db.commit()
    db.refresh(booking)

    return AdminBookingRebookingPermissionResponse(
        id=booking.id,
        status=booking.status,
        meeting_status=booking.meeting_status,
        email=booking.email,
        phone=booking.phone,
        can_schedule_again=booking.can_schedule_again,
    )