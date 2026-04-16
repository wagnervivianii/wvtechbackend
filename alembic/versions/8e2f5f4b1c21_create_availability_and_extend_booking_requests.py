"""create availability and extend booking requests

Revision ID: 8e2f5f4b1c21
Revises: 4c782c7d30af
Create Date: 2026-04-15 20:30:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "8e2f5f4b1c21"
down_revision: str | None = "4c782c7d30af"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


STATUS_OLD_DEFAULT = "received"
STATUS_NEW_DEFAULT = "pending_contact_confirmation"


def upgrade() -> None:
    op.create_table(
        "availability_days",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("available_date", sa.Date(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_availability_days_available_date"), "availability_days", ["available_date"], unique=True)
    op.create_index(op.f("ix_availability_days_is_active"), "availability_days", ["is_active"], unique=False)

    op.create_table(
        "availability_slots",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("availability_day_id", sa.Integer(), nullable=False),
        sa.Column("start_time", sa.Time(), nullable=False),
        sa.Column("end_time", sa.Time(), nullable=False),
        sa.Column("timezone_name", sa.String(length=80), server_default="America/Sao_Paulo", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["availability_day_id"], ["availability_days.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("availability_day_id", "start_time", "end_time", name="uq_availability_slots_day_time"),
    )
    op.create_index(op.f("ix_availability_slots_availability_day_id"), "availability_slots", ["availability_day_id"], unique=False)
    op.create_index(op.f("ix_availability_slots_is_active"), "availability_slots", ["is_active"], unique=False)

    op.add_column("booking_requests", sa.Column("availability_slot_id", sa.Integer(), nullable=True))
    op.add_column("booking_requests", sa.Column("booking_date", sa.Date(), nullable=True))
    op.add_column("booking_requests", sa.Column("start_time", sa.Time(), nullable=True))
    op.add_column("booking_requests", sa.Column("end_time", sa.Time(), nullable=True))

    op.create_index(op.f("ix_booking_requests_availability_slot_id"), "booking_requests", ["availability_slot_id"], unique=False)
    op.create_index(op.f("ix_booking_requests_booking_date"), "booking_requests", ["booking_date"], unique=False)
    op.create_foreign_key(
        "fk_booking_requests_availability_slot_id",
        "booking_requests",
        "availability_slots",
        ["availability_slot_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.alter_column(
        "booking_requests",
        "status",
        existing_type=sa.String(length=30),
        type_=sa.String(length=40),
        existing_nullable=False,
        existing_server_default=STATUS_OLD_DEFAULT,
        server_default=STATUS_NEW_DEFAULT,
    )


def downgrade() -> None:
    op.alter_column(
        "booking_requests",
        "status",
        existing_type=sa.String(length=40),
        type_=sa.String(length=30),
        existing_nullable=False,
        existing_server_default=STATUS_NEW_DEFAULT,
        server_default=STATUS_OLD_DEFAULT,
    )

    op.drop_constraint("fk_booking_requests_availability_slot_id", "booking_requests", type_="foreignkey")
    op.drop_index(op.f("ix_booking_requests_booking_date"), table_name="booking_requests")
    op.drop_index(op.f("ix_booking_requests_availability_slot_id"), table_name="booking_requests")
    op.drop_column("booking_requests", "end_time")
    op.drop_column("booking_requests", "start_time")
    op.drop_column("booking_requests", "booking_date")
    op.drop_column("booking_requests", "availability_slot_id")

    op.drop_index(op.f("ix_availability_slots_is_active"), table_name="availability_slots")
    op.drop_index(op.f("ix_availability_slots_availability_day_id"), table_name="availability_slots")
    op.drop_table("availability_slots")

    op.drop_index(op.f("ix_availability_days_is_active"), table_name="availability_days")
    op.drop_index(op.f("ix_availability_days_available_date"), table_name="availability_days")
    op.drop_table("availability_days")
