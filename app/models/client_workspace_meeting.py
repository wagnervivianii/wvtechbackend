from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ClientWorkspaceMeeting(Base):
    __tablename__ = "client_workspace_meetings"

    id: Mapped[int] = mapped_column(primary_key=True)
    workspace_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("client_workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    booking_request_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("booking_requests.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    meeting_label: Mapped[str] = mapped_column(String(255), nullable=False)
    meet_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    recording_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    recording_provider: Mapped[str | None] = mapped_column(String(80), nullable=True)
    recording_file_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    transcript_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    transcript_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    meeting_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    meeting_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    meeting_ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    synced_from_booking_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_visible_to_client: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )