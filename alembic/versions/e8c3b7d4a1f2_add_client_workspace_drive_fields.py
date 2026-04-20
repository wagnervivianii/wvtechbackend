"""add client workspace drive fields

Revision ID: e8c3b7d4a1f2
Revises: d1a4f8c9b2e7
Create Date: 2026-04-19 00:00:00.000000
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e8c3b7d4a1f2'
down_revision: str | None = 'd1a4f8c9b2e7'
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


DRIVE_STATUS_DEFAULT = 'pending_configuration'


def upgrade() -> None:
    op.add_column(
        'client_workspaces',
        sa.Column(
            'drive_sync_status',
            sa.String(length=40),
            nullable=False,
            server_default=DRIVE_STATUS_DEFAULT,
        ),
    )
    op.add_column('client_workspaces', sa.Column('drive_sync_error', sa.Text(), nullable=True))
    op.add_column('client_workspaces', sa.Column('drive_synced_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('client_workspaces', sa.Column('drive_root_folder_id', sa.String(length=255), nullable=True))
    op.add_column('client_workspaces', sa.Column('drive_root_folder_name', sa.String(length=255), nullable=True))
    op.add_column('client_workspaces', sa.Column('drive_root_folder_url', sa.String(length=500), nullable=True))
    op.add_column('client_workspaces', sa.Column('drive_meet_artifacts_folder_id', sa.String(length=255), nullable=True))
    op.add_column('client_workspaces', sa.Column('drive_meet_artifacts_folder_name', sa.String(length=255), nullable=True))
    op.add_column('client_workspaces', sa.Column('drive_meet_artifacts_folder_url', sa.String(length=500), nullable=True))
    op.add_column('client_workspaces', sa.Column('drive_client_uploads_folder_id', sa.String(length=255), nullable=True))
    op.add_column('client_workspaces', sa.Column('drive_client_uploads_folder_name', sa.String(length=255), nullable=True))
    op.add_column('client_workspaces', sa.Column('drive_client_uploads_folder_url', sa.String(length=500), nullable=True))
    op.add_column('client_workspaces', sa.Column('drive_generated_documents_folder_id', sa.String(length=255), nullable=True))
    op.add_column('client_workspaces', sa.Column('drive_generated_documents_folder_name', sa.String(length=255), nullable=True))
    op.add_column('client_workspaces', sa.Column('drive_generated_documents_folder_url', sa.String(length=500), nullable=True))
    op.add_column('client_workspaces', sa.Column('drive_archive_folder_id', sa.String(length=255), nullable=True))
    op.add_column('client_workspaces', sa.Column('drive_archive_folder_name', sa.String(length=255), nullable=True))
    op.add_column('client_workspaces', sa.Column('drive_archive_folder_url', sa.String(length=500), nullable=True))

    op.create_index(
        'ix_client_workspaces_drive_sync_status',
        'client_workspaces',
        ['drive_sync_status'],
        unique=False,
    )
    op.create_index(
        'ix_client_workspaces_drive_root_folder_id',
        'client_workspaces',
        ['drive_root_folder_id'],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index('ix_client_workspaces_drive_root_folder_id', table_name='client_workspaces')
    op.drop_index('ix_client_workspaces_drive_sync_status', table_name='client_workspaces')

    op.drop_column('client_workspaces', 'drive_archive_folder_url')
    op.drop_column('client_workspaces', 'drive_archive_folder_name')
    op.drop_column('client_workspaces', 'drive_archive_folder_id')
    op.drop_column('client_workspaces', 'drive_generated_documents_folder_url')
    op.drop_column('client_workspaces', 'drive_generated_documents_folder_name')
    op.drop_column('client_workspaces', 'drive_generated_documents_folder_id')
    op.drop_column('client_workspaces', 'drive_client_uploads_folder_url')
    op.drop_column('client_workspaces', 'drive_client_uploads_folder_name')
    op.drop_column('client_workspaces', 'drive_client_uploads_folder_id')
    op.drop_column('client_workspaces', 'drive_meet_artifacts_folder_url')
    op.drop_column('client_workspaces', 'drive_meet_artifacts_folder_name')
    op.drop_column('client_workspaces', 'drive_meet_artifacts_folder_id')
    op.drop_column('client_workspaces', 'drive_root_folder_url')
    op.drop_column('client_workspaces', 'drive_root_folder_name')
    op.drop_column('client_workspaces', 'drive_root_folder_id')
    op.drop_column('client_workspaces', 'drive_synced_at')
    op.drop_column('client_workspaces', 'drive_sync_error')
    op.drop_column('client_workspaces', 'drive_sync_status')
