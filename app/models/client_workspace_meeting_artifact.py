from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ClientWorkspaceMeetingArtifact(Base):
    __tablename__ = "client_workspace_meeting_artifacts"
    __table_args__ = (
        Index('ix_cwma_workspace_id', 'workspace_id'),
        Index('ix_cwma_meeting_id', 'meeting_id'),
        Index('ix_cwma_artifact_type', 'artifact_type'),
        Index('ix_cwma_artifact_status', 'artifact_status'),
        Index('ix_cwma_gconf_record', 'google_conference_record_name'),
        Index('ix_cwma_gartifact', 'google_artifact_resource_name'),
        Index('ix_cwma_drive_file_id', 'drive_file_id'),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    workspace_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("client_workspaces.id", ondelete="CASCADE"),
        nullable=False,
    )
    meeting_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("client_workspace_meetings.id", ondelete="CASCADE"),
        nullable=False,
    )
    artifact_type: Mapped[str] = mapped_column(String(40), nullable=False)
    artifact_status: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
        default="pending",
        server_default="pending",
    )
    artifact_label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_provider: Mapped[str | None] = mapped_column(String(80), nullable=True)
    google_conference_record_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    google_artifact_resource_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_download_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    drive_file_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    drive_file_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    drive_web_view_link: Mapped[str | None] = mapped_column(String(500), nullable=True)
    mime_type: Mapped[str | None] = mapped_column(String(120), nullable=True)
    file_size_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    text_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    captured_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
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
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
