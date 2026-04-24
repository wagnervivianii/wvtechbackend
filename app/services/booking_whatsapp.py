from __future__ import annotations

from datetime import datetime, timedelta
import logging
from zoneinfo import ZoneInfo

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.booking_request import BookingRequest
from app.services.notifications.whatsapp_dispatcher import WhatsAppDispatcher
from app.integrations.meta_whatsapp.schemas import WhatsAppSendResult, WhatsAppWebhookParseResult


logger = logging.getLogger(__name__)

WHATSAPP_STATUS_OPT_OUT = 'opt_out'
WHATSAPP_STATUS_SKIPPED = 'skipped'
WHATSAPP_STATUS_INBOUND_RECEIVED = 'inbound_received'

WHATSAPP_CONFIRM_KEYWORDS = frozenset(
    {
        'ok',
        'tudo certo',
        'confirmado',
        'confirmar',
        'confirmo',
        'sim',
        'presenca confirmada',
        'presença confirmada',
    }
)

WHATSAPP_CANCEL_KEYWORDS = frozenset(
    {
        'cancelar',
        'cancelado',
        'cancelar reuniao',
        'cancelar reunião',
        'nao vou conseguir',
        'não vou conseguir',
        'nao vou participar',
        'não vou participar',
    }
)


class BookingWhatsAppService:
    def __init__(self, dispatcher: WhatsAppDispatcher | None = None) -> None:
        self._dispatcher = dispatcher or WhatsAppDispatcher()

    def prepare_booking_after_approval(self, *, booking: BookingRequest) -> None:
        self._schedule_reminders(booking)

    def send_booking_approved_message(self, *, booking: BookingRequest) -> WhatsAppSendResult:
        self.prepare_booking_after_approval(booking=booking)

        if not booking.whatsapp_opt_in:
            return self._build_skipped_result(
                booking=booking,
                status=WHATSAPP_STATUS_OPT_OUT,
                error_message='Contato sem consentimento/elegibilidade para WhatsApp.',
            )

        recipient_phone = self._format_whatsapp_phone(booking.phone)
        if not recipient_phone:
            return self._build_skipped_result(
                booking=booking,
                status=WHATSAPP_STATUS_SKIPPED,
                error_message='Telefone do contato ausente ou inválido para envio WhatsApp.',
            )

        if not booking.meet_url:
            return self._build_skipped_result(
                booking=booking,
                status=WHATSAPP_STATUS_SKIPPED,
                error_message='Reunião sem link do Google Meet para enviar ao cliente.',
            )

        template_name = settings.meta_whatsapp_template_booking_confirmed
        result = self._dispatcher.send_template(
            recipient_phone=recipient_phone,
            template_name=template_name,
            body_values=(
                self._display_name(booking.name),
                self._display_date(booking),
                self._display_time(booking),
                booking.meet_url,
            ),
        )
        self._apply_send_result(booking=booking, template_name=template_name, result=result)
        return result

    def send_due_reminders(self, *, db: Session, reference_dt: datetime | None = None, limit: int = 100) -> list[int]:
        now_local = reference_dt or self._now_local()
        sent_booking_ids: list[int] = []

        due_1d_items = db.scalars(
            select(BookingRequest)
            .where(BookingRequest.status == 'approved')
            .where(BookingRequest.meeting_status == 'scheduled')
            .where(BookingRequest.whatsapp_opt_in.is_(True))
            .where(BookingRequest.whatsapp_reminder_1d_due_at.is_not(None))
            .where(BookingRequest.whatsapp_reminder_1d_due_at <= now_local)
            .where(BookingRequest.whatsapp_reminder_1d_sent_at.is_(None))
            .order_by(BookingRequest.whatsapp_reminder_1d_due_at.asc(), BookingRequest.id.asc())
            .limit(limit)
        ).all()

        for booking in due_1d_items:
            result = self._send_reminder_1d(booking=booking)
            if result.status in {'accepted', 'dry_run'}:
                sent_booking_ids.append(booking.id)
                db.add(booking)

        remaining = max(limit - len(sent_booking_ids), 0)
        if remaining > 0:
            due_15m_items = db.scalars(
                select(BookingRequest)
                .where(BookingRequest.status == 'approved')
                .where(BookingRequest.meeting_status == 'scheduled')
                .where(BookingRequest.whatsapp_opt_in.is_(True))
                .where(BookingRequest.whatsapp_reminder_15m_due_at.is_not(None))
                .where(BookingRequest.whatsapp_reminder_15m_due_at <= now_local)
                .where(BookingRequest.whatsapp_reminder_15m_sent_at.is_(None))
                .order_by(BookingRequest.whatsapp_reminder_15m_due_at.asc(), BookingRequest.id.asc())
                .limit(remaining)
            ).all()

            for booking in due_15m_items:
                result = self._send_reminder_15m(booking=booking)
                if result.status in {'accepted', 'dry_run'}:
                    sent_booking_ids.append(booking.id)
                    db.add(booking)

        if sent_booking_ids:
            db.commit()

        return sent_booking_ids

    def process_webhook_events(self, *, db: Session, parse_result: WhatsAppWebhookParseResult) -> int:
        changes = 0

        for status_event in parse_result.status_events:
            booking = self._find_booking_for_status_event(db=db, message_id=status_event.message_id, recipient_phone=status_event.recipient_id)
            if booking is None:
                continue

            booking.whatsapp_last_status = status_event.status
            if status_event.message_id:
                booking.whatsapp_last_message_id = status_event.message_id
            changes += 1
            db.add(booking)

        for message_event in parse_result.message_events:
            booking = self._find_latest_booking_by_phone(db=db, phone=message_event.from_phone)
            if booking is None:
                continue

            inbound_text = (message_event.text_body or '').strip() or None
            booking.whatsapp_last_status = WHATSAPP_STATUS_INBOUND_RECEIVED
            booking.whatsapp_last_inbound_text = inbound_text
            booking.whatsapp_last_inbound_at = self._now_local()

            normalized_text = self._normalize_inbound_text(inbound_text)
            if normalized_text in WHATSAPP_CONFIRM_KEYWORDS:
                booking.whatsapp_confirmed_at = booking.whatsapp_last_inbound_at
            elif normalized_text in WHATSAPP_CANCEL_KEYWORDS:
                booking.whatsapp_cancelled_at = booking.whatsapp_last_inbound_at

            changes += 1
            db.add(booking)

        if changes:
            db.commit()

        return changes

    def _send_reminder_1d(self, *, booking: BookingRequest) -> WhatsAppSendResult:
        recipient_phone = self._format_whatsapp_phone(booking.phone)
        if not recipient_phone:
            return self._build_skipped_result(
                booking=booking,
                status=WHATSAPP_STATUS_SKIPPED,
                error_message='Telefone do contato ausente ou inválido para lembrete de 1 dia.',
            )

        template_name = settings.meta_whatsapp_template_booking_reminder_1d
        result = self._dispatcher.send_template(
            recipient_phone=recipient_phone,
            template_name=template_name,
            body_values=(
                self._display_name(booking.name),
                self._display_date(booking),
                self._display_time(booking),
            ),
        )
        self._apply_send_result(booking=booking, template_name=template_name, result=result)
        if result.status in {'accepted', 'dry_run'}:
            booking.whatsapp_reminder_1d_sent_at = self._now_local()
        return result

    def _send_reminder_15m(self, *, booking: BookingRequest) -> WhatsAppSendResult:
        recipient_phone = self._format_whatsapp_phone(booking.phone)
        if not recipient_phone:
            return self._build_skipped_result(
                booking=booking,
                status=WHATSAPP_STATUS_SKIPPED,
                error_message='Telefone do contato ausente ou inválido para lembrete de 15 minutos.',
            )

        if not booking.meet_url:
            return self._build_skipped_result(
                booking=booking,
                status=WHATSAPP_STATUS_SKIPPED,
                error_message='Reunião sem link do Google Meet para lembrete de 15 minutos.',
            )

        template_name = settings.meta_whatsapp_template_booking_reminder_15m
        result = self._dispatcher.send_template(
            recipient_phone=recipient_phone,
            template_name=template_name,
            body_values=(
                self._display_name(booking.name),
                self._display_time(booking),
                booking.meet_url,
            ),
        )
        self._apply_send_result(booking=booking, template_name=template_name, result=result)
        if result.status in {'accepted', 'dry_run'}:
            booking.whatsapp_reminder_15m_sent_at = self._now_local()
        return result

    def _build_skipped_result(self, *, booking: BookingRequest, status: str, error_message: str) -> WhatsAppSendResult:
        booking.whatsapp_last_status = status
        booking.whatsapp_last_error = error_message
        booking.whatsapp_last_sent_at = self._now_local()
        return WhatsAppSendResult(
            message_id=None,
            status=status,
            recipient_phone=self._format_whatsapp_phone(booking.phone) or booking.phone,
            raw_response={'reason': error_message},
        )

    def _apply_send_result(self, *, booking: BookingRequest, template_name: str, result: WhatsAppSendResult) -> None:
        now_local = self._now_local()
        booking.whatsapp_last_template_name = template_name
        booking.whatsapp_last_message_id = result.message_id
        booking.whatsapp_last_sent_at = now_local
        booking.whatsapp_last_status = result.status
        booking.whatsapp_last_error = self._extract_result_error(result)

    def _extract_result_error(self, result: WhatsAppSendResult) -> str | None:
        reason = result.raw_response.get('reason') if isinstance(result.raw_response, dict) else None
        if isinstance(reason, str) and reason.strip():
            return reason.strip()
        return None

    def _schedule_reminders(self, booking: BookingRequest) -> None:
        booking_start = self._booking_start_datetime(booking)
        if booking_start is None:
            booking.whatsapp_reminder_1d_due_at = None
            booking.whatsapp_reminder_15m_due_at = None
            return

        now_local = self._now_local()
        reminder_1d_due_at = booking_start - timedelta(days=1)
        reminder_15m_due_at = booking_start - timedelta(minutes=15)

        booking.whatsapp_reminder_1d_due_at = reminder_1d_due_at if reminder_1d_due_at > now_local else None
        booking.whatsapp_reminder_15m_due_at = reminder_15m_due_at if reminder_15m_due_at > now_local else None

    def _booking_start_datetime(self, booking: BookingRequest) -> datetime | None:
        if booking.booking_date is None or booking.start_time is None:
            return None
        return datetime.combine(
            booking.booking_date,
            booking.start_time,
            tzinfo=ZoneInfo(settings.app_timezone),
        )

    def _find_booking_for_status_event(self, *, db: Session, message_id: str | None, recipient_phone: str | None) -> BookingRequest | None:
        if message_id:
            booking = db.scalar(
                select(BookingRequest)
                .where(BookingRequest.whatsapp_last_message_id == message_id)
                .order_by(BookingRequest.created_at.desc(), BookingRequest.id.desc())
            )
            if booking is not None:
                return booking

        return self._find_latest_booking_by_phone(db=db, phone=recipient_phone)

    def _find_latest_booking_by_phone(self, *, db: Session, phone: str | None) -> BookingRequest | None:
        candidates = self._phone_candidates(phone)
        if not candidates:
            return None

        return db.scalar(
            select(BookingRequest)
            .where(or_(*[BookingRequest.phone == item for item in candidates]))
            .order_by(BookingRequest.created_at.desc(), BookingRequest.id.desc())
        )

    def _phone_candidates(self, phone: str | None) -> tuple[str, ...]:
        digits = ''.join(char for char in (phone or '') if char.isdigit())
        if not digits:
            return ()

        candidates: list[str] = [digits]
        if digits.startswith('55') and len(digits) in (12, 13):
            candidates.append(digits[2:])
        elif len(digits) in (10, 11):
            candidates.append(f'55{digits}')

        unique_candidates: list[str] = []
        for item in candidates:
            if item not in unique_candidates:
                unique_candidates.append(item)
        return tuple(unique_candidates)

    def _format_whatsapp_phone(self, raw_phone: str | None) -> str | None:
        digits = ''.join(char for char in (raw_phone or '') if char.isdigit())
        if not digits:
            return None
        if digits.startswith('55') and len(digits) in (12, 13):
            return digits
        if len(digits) in (10, 11):
            return f'55{digits}'
        return digits

    def _display_name(self, raw_name: str | None) -> str:
        value = ' '.join((raw_name or '').strip().split())
        return value.title() or 'Cliente'

    def _display_date(self, booking: BookingRequest) -> str:
        return booking.booking_date.strftime('%d/%m/%Y') if booking.booking_date else 'Data a confirmar'

    def _display_time(self, booking: BookingRequest) -> str:
        return booking.start_time.strftime('%H:%M') if booking.start_time else 'Horário a confirmar'

    def _normalize_inbound_text(self, text: str | None) -> str:
        normalized = ' '.join((text or '').strip().lower().split())
        return normalized

    def _now_local(self) -> datetime:
        return datetime.now(ZoneInfo(settings.app_timezone))
