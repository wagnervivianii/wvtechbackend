from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ClientWorkspaceInvite(Base):
    __tablename__ = "client_workspace_invites"

    id: Mapped[int] = mapped_column(primary_key=True)
    workspace_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("client_workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    invite_email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    invite_token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    invite_status: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
        default="pending",
        server_default="pending",
        index=True,
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )