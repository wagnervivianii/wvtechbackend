"""prepare booking history and meet fields

Revision ID: b7d4b2c1f0a9
Revises: 8e2f5f4b1c21
Create Date: 2026-04-16 20:10:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "b7d4b2c1f0a9"
down_revision: str | None = "8e2f5f4b1c21"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "booking_requests",
        sa.Column(
            "meeting_status",
            sa.String(length=40),
            nullable=False,
            server_default="scheduled",
        ),
    )
    op.add_column(
        "booking_requests",
        sa.Column("meet_event_id", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "booking_requests",
        sa.Column("meet_url", sa.String(length=500), nullable=True),
    )
    op.add_column(
        "booking_requests",
        sa.Column("meeting_notes", sa.Text(), nullable=True),
    )
    op.add_column(
        "booking_requests",
        sa.Column("transcript_text", sa.Text(), nullable=True),
    )
    op.add_column(
        "booking_requests",
        sa.Column("transcript_summary", sa.Text(), nullable=True),
    )
    op.add_column(
        "booking_requests",
        sa.Column("meeting_started_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "booking_requests",
        sa.Column("meeting_ended_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_index(
        op.f("ix_booking_requests_meeting_status"),
        "booking_requests",
        ["meeting_status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_booking_requests_meet_event_id"),
        "booking_requests",
        ["meet_event_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_booking_requests_meet_event_id"), table_name="booking_requests")
    op.drop_index(op.f("ix_booking_requests_meeting_status"), table_name="booking_requests")

    op.drop_column("booking_requests", "meeting_ended_at")
    op.drop_column("booking_requests", "meeting_started_at")
    op.drop_column("booking_requests", "transcript_summary")
    op.drop_column("booking_requests", "transcript_text")
    op.drop_column("booking_requests", "meeting_notes")
    op.drop_column("booking_requests", "meet_url")
    op.drop_column("booking_requests", "meet_event_id")
    op.drop_column("booking_requests", "meeting_status")
