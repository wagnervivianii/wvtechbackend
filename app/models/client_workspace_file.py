from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ClientWorkspaceFile(Base):
    __tablename__ = "client_workspace_files"
    __table_args__ = (
        Index("ix_cwf_workspace_id", "workspace_id"),
        Index("ix_cwf_meeting_id", "meeting_id"),
        Index("ix_cwf_review_status", "review_status"),
        Index("ix_cwf_visibility_scope", "visibility_scope"),
        Index("ix_cwf_category", "file_category"),
        Index("ix_cwf_drive_file_id", "drive_file_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    workspace_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("client_workspaces.id", ondelete="CASCADE"),
        nullable=False,
    )
    meeting_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("client_workspace_meetings.id", ondelete="SET NULL"),
        nullable=True,
    )
    uploaded_by_role: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
        default="client",
        server_default="client",
    )
    uploaded_by_account_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("client_workspace_accounts.id", ondelete="SET NULL"),
        nullable=True,
    )
    file_category: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
        default="client_upload",
        server_default="client_upload",
    )
    review_status: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
        default="pending_review",
        server_default="pending_review",
    )
    visibility_scope: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
        default="admin_only",
        server_default="admin_only",
    )
    display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    drive_file_id: Mapped[str] = mapped_column(String(255), nullable=False)
    drive_file_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    drive_web_view_link: Mapped[str | None] = mapped_column(String(500), nullable=True)
    drive_folder_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    mime_type: Mapped[str | None] = mapped_column(String(160), nullable=True)
    file_extension: Mapped[str | None] = mapped_column(String(20), nullable=True)
    file_size_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    checksum_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    review_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
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
