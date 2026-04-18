"""add confirmation access count

Revision ID: a7b9c1d3e5f7
Revises: f6b2d19a7e43
Create Date: 2026-04-18 12:30:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "a7b9c1d3e5f7"
down_revision: str | None = "f6b2d19a7e43"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "booking_request_confirmations",
        sa.Column(
            "confirmation_access_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )


def downgrade() -> None:
    op.drop_column("booking_request_confirmations", "confirmation_access_count")