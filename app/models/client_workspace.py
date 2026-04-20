from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ClientWorkspace(Base):
    __tablename__ = "client_workspaces"

    id: Mapped[int] = mapped_column(primary_key=True)
    source_booking_request_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("booking_requests.id", ondelete="SET NULL"),
        nullable=True,
        unique=True,
        index=True,
    )
    primary_contact_name: Mapped[str] = mapped_column(String(120), nullable=False)
    primary_contact_email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    primary_contact_phone: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    workspace_status: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
        default="provisioned",
        server_default="provisioned",
        index=True,
    )
    portal_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    drive_sync_status: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
        default='pending_configuration',
        server_default='pending_configuration',
        index=True,
    )
    drive_sync_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    drive_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    drive_root_folder_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    drive_root_folder_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    drive_root_folder_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    drive_meet_artifacts_folder_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    drive_meet_artifacts_folder_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    drive_meet_artifacts_folder_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    drive_client_uploads_folder_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    drive_client_uploads_folder_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    drive_client_uploads_folder_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    drive_generated_documents_folder_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    drive_generated_documents_folder_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    drive_generated_documents_folder_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    drive_archive_folder_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    drive_archive_folder_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    drive_archive_folder_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )