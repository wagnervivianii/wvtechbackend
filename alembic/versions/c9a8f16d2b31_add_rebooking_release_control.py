"""add rebooking release control

Revision ID: c9a8f16d2b31
Revises: b7d4b2c1f0a9
Create Date: 2026-04-17 00:00:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "c9a8f16d2b31"
down_revision: str | None = "b7d4b2c1f0a9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "booking_requests",
        sa.Column(
            "can_schedule_again",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.create_index(
        op.f("ix_booking_requests_can_schedule_again"),
        "booking_requests",
        ["can_schedule_again"],
        unique=False,
    )
    op.create_index(
        "ix_booking_requests_email_phone_created_at",
        "booking_requests",
        ["email", "phone", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_booking_requests_email_phone_created_at", table_name="booking_requests")
    op.drop_index(op.f("ix_booking_requests_can_schedule_again"), table_name="booking_requests")
    op.drop_column("booking_requests", "can_schedule_again")