"""add booking confirmation and admin review flow

Revision ID: f6b2d19a7e43
Revises: e3f1a9b6c4d2
Create Date: 2026-04-17 11:20:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "f6b2d19a7e43"
down_revision: str | None = "e3f1a9b6c4d2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "booking_requests",
        sa.Column("contact_confirmed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "booking_requests",
        sa.Column("admin_reviewed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "booking_requests",
        sa.Column("rejection_reason", sa.Text(), nullable=True),
    )
    op.create_index(
        op.f("ix_booking_requests_contact_confirmed_at"),
        "booking_requests",
        ["contact_confirmed_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_booking_requests_admin_reviewed_at"),
        "booking_requests",
        ["admin_reviewed_at"],
        unique=False,
    )

    op.create_table(
        "booking_request_confirmations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("booking_request_id", sa.Integer(), nullable=False),
        sa.Column("confirmation_token_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "confirmation_status",
            sa.String(length=40),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(["booking_request_id"], ["booking_requests.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("confirmation_token_hash"),
    )
    op.create_index(
        op.f("ix_booking_request_confirmations_booking_request_id"),
        "booking_request_confirmations",
        ["booking_request_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_booking_request_confirmations_confirmation_token_hash"),
        "booking_request_confirmations",
        ["confirmation_token_hash"],
        unique=True,
    )
    op.create_index(
        op.f("ix_booking_request_confirmations_confirmation_status"),
        "booking_request_confirmations",
        ["confirmation_status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_booking_request_confirmations_confirmation_status"),
        table_name="booking_request_confirmations",
    )
    op.drop_index(
        op.f("ix_booking_request_confirmations_confirmation_token_hash"),
        table_name="booking_request_confirmations",
    )
    op.drop_index(
        op.f("ix_booking_request_confirmations_booking_request_id"),
        table_name="booking_request_confirmations",
    )
    op.drop_table("booking_request_confirmations")

    op.drop_index(op.f("ix_booking_requests_admin_reviewed_at"), table_name="booking_requests")
    op.drop_index(op.f("ix_booking_requests_contact_confirmed_at"), table_name="booking_requests")
    op.drop_column("booking_requests", "rejection_reason")
    op.drop_column("booking_requests", "admin_reviewed_at")
    op.drop_column("booking_requests", "contact_confirmed_at")