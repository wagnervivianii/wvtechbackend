from datetime import date, datetime, time

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, Text, Time, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class BookingRequest(Base):
    __tablename__ = 'booking_requests'

    id: Mapped[int] = mapped_column(primary_key=True)
    slot_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    availability_slot_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey('availability_slots.id', ondelete='SET NULL'),
        nullable=True,
        index=True,
    )
    booking_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    start_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    end_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    phone: Mapped[str] = mapped_column(String(30), nullable=False)
    subject_summary: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
        default='pending_contact_confirmation',
        server_default='pending_contact_confirmation',
        index=True,
    )
    meeting_status: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
        default='scheduled',
        server_default='scheduled',
        index=True,
    )
    meet_event_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    meet_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    meeting_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    transcript_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    transcript_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    meeting_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    meeting_ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    can_schedule_again: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default='false',
        index=True,
    )
    whatsapp_opt_in: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default='true',
        index=True,
    )
    whatsapp_last_template_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    whatsapp_last_message_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    whatsapp_last_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    whatsapp_last_status: Mapped[str | None] = mapped_column(String(60), nullable=True, index=True)
    whatsapp_last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    whatsapp_last_inbound_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    whatsapp_last_inbound_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    whatsapp_confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    whatsapp_cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    whatsapp_reminder_1d_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    whatsapp_reminder_1d_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    whatsapp_reminder_15m_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    whatsapp_reminder_15m_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    contact_confirmed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )
    admin_reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
