from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = 'c3f7d2a9b1e4'
down_revision = 'aa41c3d9e7b2'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'booking_requests',
        sa.Column('whatsapp_opt_in', sa.Boolean(), nullable=False, server_default=sa.text('true')),
    )
    op.add_column('booking_requests', sa.Column('whatsapp_last_template_name', sa.String(length=120), nullable=True))
    op.add_column('booking_requests', sa.Column('whatsapp_last_message_id', sa.String(length=255), nullable=True))
    op.add_column('booking_requests', sa.Column('whatsapp_last_sent_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('booking_requests', sa.Column('whatsapp_last_status', sa.String(length=60), nullable=True))
    op.add_column('booking_requests', sa.Column('whatsapp_last_error', sa.Text(), nullable=True))
    op.add_column('booking_requests', sa.Column('whatsapp_last_inbound_text', sa.Text(), nullable=True))
    op.add_column('booking_requests', sa.Column('whatsapp_last_inbound_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('booking_requests', sa.Column('whatsapp_confirmed_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('booking_requests', sa.Column('whatsapp_cancelled_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('booking_requests', sa.Column('whatsapp_reminder_1d_due_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('booking_requests', sa.Column('whatsapp_reminder_1d_sent_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('booking_requests', sa.Column('whatsapp_reminder_15m_due_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('booking_requests', sa.Column('whatsapp_reminder_15m_sent_at', sa.DateTime(timezone=True), nullable=True))

    op.create_index('ix_booking_requests_whatsapp_opt_in', 'booking_requests', ['whatsapp_opt_in'])
    op.create_index('ix_booking_requests_whatsapp_last_message_id', 'booking_requests', ['whatsapp_last_message_id'])
    op.create_index('ix_booking_requests_whatsapp_last_status', 'booking_requests', ['whatsapp_last_status'])


def downgrade() -> None:
    op.drop_index('ix_booking_requests_whatsapp_last_status', table_name='booking_requests')
    op.drop_index('ix_booking_requests_whatsapp_last_message_id', table_name='booking_requests')
    op.drop_index('ix_booking_requests_whatsapp_opt_in', table_name='booking_requests')

    op.drop_column('booking_requests', 'whatsapp_reminder_15m_sent_at')
    op.drop_column('booking_requests', 'whatsapp_reminder_15m_due_at')
    op.drop_column('booking_requests', 'whatsapp_reminder_1d_sent_at')
    op.drop_column('booking_requests', 'whatsapp_reminder_1d_due_at')
    op.drop_column('booking_requests', 'whatsapp_cancelled_at')
    op.drop_column('booking_requests', 'whatsapp_confirmed_at')
    op.drop_column('booking_requests', 'whatsapp_last_inbound_at')
    op.drop_column('booking_requests', 'whatsapp_last_inbound_text')
    op.drop_column('booking_requests', 'whatsapp_last_error')
    op.drop_column('booking_requests', 'whatsapp_last_status')
    op.drop_column('booking_requests', 'whatsapp_last_sent_at')
    op.drop_column('booking_requests', 'whatsapp_last_message_id')
    op.drop_column('booking_requests', 'whatsapp_last_template_name')
    op.drop_column('booking_requests', 'whatsapp_opt_in')
