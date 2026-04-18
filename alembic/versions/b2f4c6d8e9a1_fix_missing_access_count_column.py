"""fix missing access_count column on booking_request_confirmations

Revision ID: b2f4c6d8e9a1
Revises: a7b9c1d3e5f7
Create Date: 2026-04-18 13:00:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = 'b2f4c6d8e9a1'
down_revision: str | None = 'a7b9c1d3e5f7'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _get_column_names(table_name: str) -> set[str]:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return {column['name'] for column in inspector.get_columns(table_name)}


def upgrade() -> None:
    column_names = _get_column_names('booking_request_confirmations')

    if 'access_count' not in column_names:
        op.add_column(
            'booking_request_confirmations',
            sa.Column(
                'access_count',
                sa.Integer(),
                nullable=True,
                server_default='0',
            ),
        )

    op.execute(
        """
        UPDATE booking_request_confirmations
        SET access_count = 0
        WHERE access_count IS NULL
        """
    )

    op.alter_column(
        'booking_request_confirmations',
        'access_count',
        existing_type=sa.Integer(),
        nullable=False,
        server_default='0',
    )


def downgrade() -> None:
    column_names = _get_column_names('booking_request_confirmations')
    if 'access_count' in column_names:
        op.drop_column('booking_request_confirmations', 'access_count')