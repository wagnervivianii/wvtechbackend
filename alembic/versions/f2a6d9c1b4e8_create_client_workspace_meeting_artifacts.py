"""create client workspace meeting artifacts

Revision ID: f2a6d9c1b4e8
Revises: e8c3b7d4a1f2
Create Date: 2026-04-20 00:15:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = 'f2a6d9c1b4e8'
down_revision = 'e8c3b7d4a1f2'
branch_labels = None
depends_on = None


TABLE_NAME = 'client_workspace_meeting_artifacts'
IX_WORKSPACE_ID = 'ix_cwma_workspace_id'
IX_MEETING_ID = 'ix_cwma_meeting_id'
IX_ARTIFACT_TYPE = 'ix_cwma_artifact_type'
IX_ARTIFACT_STATUS = 'ix_cwma_artifact_status'
IX_GOOGLE_CONF_RECORD = 'ix_cwma_gconf_record'
IX_GOOGLE_ARTIFACT = 'ix_cwma_gartifact'
IX_DRIVE_FILE_ID = 'ix_cwma_drive_file_id'


def upgrade() -> None:
    op.create_table(
        TABLE_NAME,
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('workspace_id', sa.Integer(), nullable=False),
        sa.Column('meeting_id', sa.Integer(), nullable=False),
        sa.Column('artifact_type', sa.String(length=40), nullable=False),
        sa.Column('artifact_status', sa.String(length=40), nullable=False, server_default='pending'),
        sa.Column('artifact_label', sa.String(length=255), nullable=True),
        sa.Column('source_provider', sa.String(length=80), nullable=True),
        sa.Column('google_conference_record_name', sa.String(length=255), nullable=True),
        sa.Column('google_artifact_resource_name', sa.String(length=255), nullable=True),
        sa.Column('source_download_url', sa.String(length=500), nullable=True),
        sa.Column('drive_file_id', sa.String(length=255), nullable=True),
        sa.Column('drive_file_name', sa.String(length=255), nullable=True),
        sa.Column('drive_web_view_link', sa.String(length=500), nullable=True),
        sa.Column('mime_type', sa.String(length=120), nullable=True),
        sa.Column('file_size_bytes', sa.BigInteger(), nullable=True),
        sa.Column('text_content', sa.Text(), nullable=True),
        sa.Column('summary_text', sa.Text(), nullable=True),
        sa.Column('metadata_json', sa.JSON(), nullable=True),
        sa.Column('captured_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_synced_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_visible_to_client', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['workspace_id'], ['client_workspaces.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['meeting_id'], ['client_workspace_meetings.id'], ondelete='CASCADE'),
    )
    op.create_index(IX_WORKSPACE_ID, TABLE_NAME, ['workspace_id'])
    op.create_index(IX_MEETING_ID, TABLE_NAME, ['meeting_id'])
    op.create_index(IX_ARTIFACT_TYPE, TABLE_NAME, ['artifact_type'])
    op.create_index(IX_ARTIFACT_STATUS, TABLE_NAME, ['artifact_status'])
    op.create_index(IX_GOOGLE_CONF_RECORD, TABLE_NAME, ['google_conference_record_name'])
    op.create_index(IX_GOOGLE_ARTIFACT, TABLE_NAME, ['google_artifact_resource_name'])
    op.create_index(IX_DRIVE_FILE_ID, TABLE_NAME, ['drive_file_id'])


def downgrade() -> None:
    op.drop_index(IX_DRIVE_FILE_ID, table_name=TABLE_NAME)
    op.drop_index(IX_GOOGLE_ARTIFACT, table_name=TABLE_NAME)
    op.drop_index(IX_GOOGLE_CONF_RECORD, table_name=TABLE_NAME)
    op.drop_index(IX_ARTIFACT_STATUS, table_name=TABLE_NAME)
    op.drop_index(IX_ARTIFACT_TYPE, table_name=TABLE_NAME)
    op.drop_index(IX_MEETING_ID, table_name=TABLE_NAME)
    op.drop_index(IX_WORKSPACE_ID, table_name=TABLE_NAME)
    op.drop_table(TABLE_NAME)
