from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "aa41c3d9e7b2"
down_revision = "f2a6d9c1b4e8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "client_workspace_files",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("workspace_id", sa.Integer(), nullable=False),
        sa.Column("meeting_id", sa.Integer(), nullable=True),
        sa.Column("uploaded_by_role", sa.String(length=40), nullable=False, server_default="client"),
        sa.Column("uploaded_by_account_id", sa.Integer(), nullable=True),
        sa.Column("file_category", sa.String(length=40), nullable=False, server_default="client_upload"),
        sa.Column("review_status", sa.String(length=40), nullable=False, server_default="pending_review"),
        sa.Column("visibility_scope", sa.String(length=40), nullable=False, server_default="admin_only"),
        sa.Column("display_name", sa.String(length=255), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("drive_file_id", sa.String(length=255), nullable=False),
        sa.Column("drive_file_name", sa.String(length=255), nullable=True),
        sa.Column("drive_web_view_link", sa.String(length=500), nullable=True),
        sa.Column("drive_folder_id", sa.String(length=255), nullable=True),
        sa.Column("mime_type", sa.String(length=160), nullable=True),
        sa.Column("file_extension", sa.String(length=20), nullable=True),
        sa.Column("file_size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("checksum_sha256", sa.String(length=64), nullable=True),
        sa.Column("review_notes", sa.Text(), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["workspace_id"], ["client_workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["meeting_id"], ["client_workspace_meetings.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["uploaded_by_account_id"], ["client_workspace_accounts.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_cwf_workspace_id", "client_workspace_files", ["workspace_id"])
    op.create_index("ix_cwf_meeting_id", "client_workspace_files", ["meeting_id"])
    op.create_index("ix_cwf_review_status", "client_workspace_files", ["review_status"])
    op.create_index("ix_cwf_visibility_scope", "client_workspace_files", ["visibility_scope"])
    op.create_index("ix_cwf_category", "client_workspace_files", ["file_category"])
    op.create_index("ix_cwf_drive_file_id", "client_workspace_files", ["drive_file_id"])


def downgrade() -> None:
    op.drop_index("ix_cwf_drive_file_id", table_name="client_workspace_files")
    op.drop_index("ix_cwf_category", table_name="client_workspace_files")
    op.drop_index("ix_cwf_visibility_scope", table_name="client_workspace_files")
    op.drop_index("ix_cwf_review_status", table_name="client_workspace_files")
    op.drop_index("ix_cwf_meeting_id", table_name="client_workspace_files")
    op.drop_index("ix_cwf_workspace_id", table_name="client_workspace_files")
    op.drop_table("client_workspace_files")
