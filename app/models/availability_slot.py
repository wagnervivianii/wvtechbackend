from datetime import datetime, time

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Time, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AvailabilitySlot(Base):
    __tablename__ = "availability_slots"
    __table_args__ = (
        UniqueConstraint(
            "availability_day_id",
            "start_time",
            "end_time",
            name="uq_availability_slots_day_time",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    availability_day_id: Mapped[int] = mapped_column(
        ForeignKey("availability_days.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)
    timezone_name: Mapped[str] = mapped_column(
        String(80),
        nullable=False,
        default="America/Sao_Paulo",
        server_default="America/Sao_Paulo",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
