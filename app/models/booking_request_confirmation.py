from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class BookingRequestConfirmation(Base):
    __tablename__ = 'booking_request_confirmations'

    id: Mapped[int] = mapped_column(primary_key=True)
    booking_request_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey('booking_requests.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )
    confirmation_token_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        unique=True,
        index=True,
    )
    confirmation_status: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
        default='pending',
        server_default='pending',
        index=True,
    )
    access_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default='0',
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )