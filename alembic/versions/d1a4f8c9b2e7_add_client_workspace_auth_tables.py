"""add client workspace auth tables

Revision ID: d1a4f8c9b2e7
Revises: b2f4c6d8e9a1
Create Date: 2026-04-19 00:00:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = 'd1a4f8c9b2e7'
down_revision: str | None = 'b2f4c6d8e9a1'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'client_workspace_accounts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('workspace_id', sa.Integer(), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('full_name', sa.String(length=160), nullable=True),
        sa.Column('password_hash', sa.String(length=500), nullable=True),
        sa.Column('google_subject', sa.String(length=255), nullable=True),
        sa.Column('google_email', sa.String(length=255), nullable=True),
        sa.Column('google_picture_url', sa.String(length=500), nullable=True),
        sa.Column('last_login_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['workspace_id'], ['client_workspaces.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('workspace_id'),
        sa.UniqueConstraint('email'),
        sa.UniqueConstraint('google_subject'),
    )
    op.create_index(op.f('ix_client_workspace_accounts_workspace_id'), 'client_workspace_accounts', ['workspace_id'], unique=False)
    op.create_index(op.f('ix_client_workspace_accounts_email'), 'client_workspace_accounts', ['email'], unique=False)
    op.create_index(op.f('ix_client_workspace_accounts_google_subject'), 'client_workspace_accounts', ['google_subject'], unique=False)

    op.create_table(
        'client_workspace_password_reset_tokens',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('account_id', sa.Integer(), nullable=False),
        sa.Column('token_hash', sa.String(length=64), nullable=False),
        sa.Column('token_type', sa.String(length=40), server_default='password_reset', nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('sent_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('used_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['account_id'], ['client_workspace_accounts.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('token_hash'),
    )
    op.create_index(op.f('ix_client_workspace_password_reset_tokens_account_id'), 'client_workspace_password_reset_tokens', ['account_id'], unique=False)
    op.create_index(op.f('ix_client_workspace_password_reset_tokens_token_hash'), 'client_workspace_password_reset_tokens', ['token_hash'], unique=False)
    op.create_index(op.f('ix_client_workspace_password_reset_tokens_token_type'), 'client_workspace_password_reset_tokens', ['token_type'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_client_workspace_password_reset_tokens_token_type'), table_name='client_workspace_password_reset_tokens')
    op.drop_index(op.f('ix_client_workspace_password_reset_tokens_token_hash'), table_name='client_workspace_password_reset_tokens')
    op.drop_index(op.f('ix_client_workspace_password_reset_tokens_account_id'), table_name='client_workspace_password_reset_tokens')
    op.drop_table('client_workspace_password_reset_tokens')

    op.drop_index(op.f('ix_client_workspace_accounts_google_subject'), table_name='client_workspace_accounts')
    op.drop_index(op.f('ix_client_workspace_accounts_email'), table_name='client_workspace_accounts')
    op.drop_index(op.f('ix_client_workspace_accounts_workspace_id'), table_name='client_workspace_accounts')
    op.drop_table('client_workspace_accounts')