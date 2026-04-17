"""create client workspaces foundation

Revision ID: e3f1a9b6c4d2
Revises: c9a8f16d2b31
Create Date: 2026-04-17 00:40:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "e3f1a9b6c4d2"
down_revision: str | None = "c9a8f16d2b31"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "client_workspaces",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source_booking_request_id", sa.Integer(), nullable=True),
        sa.Column("primary_contact_name", sa.String(length=120), nullable=False),
        sa.Column("primary_contact_email", sa.String(length=255), nullable=False),
        sa.Column("primary_contact_phone", sa.String(length=30), nullable=False),
        sa.Column(
            "workspace_status",
            sa.String(length=40),
            nullable=False,
            server_default="provisioned",
        ),
        sa.Column("portal_notes", sa.Text(), nullable=True),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["source_booking_request_id"],
            ["booking_requests.id"],
            ondelete="SET NULL",
        ),
        sa.UniqueConstraint("source_booking_request_id"),
    )
    op.create_index(
        op.f("ix_client_workspaces_source_booking_request_id"),
        "client_workspaces",
        ["source_booking_request_id"],
        unique=True,
    )
    op.create_index(
        op.f("ix_client_workspaces_primary_contact_email"),
        "client_workspaces",
        ["primary_contact_email"],
        unique=False,
    )
    op.create_index(
        op.f("ix_client_workspaces_primary_contact_phone"),
        "client_workspaces",
        ["primary_contact_phone"],
        unique=False,
    )
    op.create_index(
        op.f("ix_client_workspaces_workspace_status"),
        "client_workspaces",
        ["workspace_status"],
        unique=False,
    )
    op.create_index(
        "ix_client_workspaces_contact_lookup",
        "client_workspaces",
        ["primary_contact_email", "primary_contact_phone", "created_at"],
        unique=False,
    )

    op.create_table(
        "client_workspace_invites",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("workspace_id", sa.Integer(), nullable=False),
        sa.Column("invite_email", sa.String(length=255), nullable=False),
        sa.Column("invite_token_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "invite_status",
            sa.String(length=40),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(["workspace_id"], ["client_workspaces.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("invite_token_hash"),
    )
    op.create_index(
        op.f("ix_client_workspace_invites_workspace_id"),
        "client_workspace_invites",
        ["workspace_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_client_workspace_invites_invite_email"),
        "client_workspace_invites",
        ["invite_email"],
        unique=False,
    )
    op.create_index(
        op.f("ix_client_workspace_invites_invite_token_hash"),
        "client_workspace_invites",
        ["invite_token_hash"],
        unique=True,
    )
    op.create_index(
        op.f("ix_client_workspace_invites_invite_status"),
        "client_workspace_invites",
        ["invite_status"],
        unique=False,
    )

    op.create_table(
        "client_workspace_meetings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("workspace_id", sa.Integer(), nullable=False),
        sa.Column("booking_request_id", sa.Integer(), nullable=False),
        sa.Column("meeting_label", sa.String(length=255), nullable=False),
        sa.Column("meet_url", sa.String(length=500), nullable=True),
        sa.Column("recording_url", sa.String(length=500), nullable=True),
        sa.Column("recording_provider", sa.String(length=80), nullable=True),
        sa.Column("recording_file_id", sa.String(length=255), nullable=True),
        sa.Column("transcript_text", sa.Text(), nullable=True),
        sa.Column("transcript_summary", sa.Text(), nullable=True),
        sa.Column("meeting_notes", sa.Text(), nullable=True),
        sa.Column("meeting_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("meeting_ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("synced_from_booking_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "is_visible_to_client",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(["workspace_id"], ["client_workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["booking_request_id"], ["booking_requests.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("booking_request_id"),
    )
    op.create_index(
        op.f("ix_client_workspace_meetings_workspace_id"),
        "client_workspace_meetings",
        ["workspace_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_client_workspace_meetings_booking_request_id"),
        "client_workspace_meetings",
        ["booking_request_id"],
        unique=True,
    )
    op.create_index(
        op.f("ix_client_workspace_meetings_recording_file_id"),
        "client_workspace_meetings",
        ["recording_file_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_client_workspace_meetings_recording_file_id"), table_name="client_workspace_meetings")
    op.drop_index(op.f("ix_client_workspace_meetings_booking_request_id"), table_name="client_workspace_meetings")
    op.drop_index(op.f("ix_client_workspace_meetings_workspace_id"), table_name="client_workspace_meetings")
    op.drop_table("client_workspace_meetings")

    op.drop_index(op.f("ix_client_workspace_invites_invite_status"), table_name="client_workspace_invites")
    op.drop_index(op.f("ix_client_workspace_invites_invite_token_hash"), table_name="client_workspace_invites")
    op.drop_index(op.f("ix_client_workspace_invites_invite_email"), table_name="client_workspace_invites")
    op.drop_index(op.f("ix_client_workspace_invites_workspace_id"), table_name="client_workspace_invites")
    op.drop_table("client_workspace_invites")

    op.drop_index("ix_client_workspaces_contact_lookup", table_name="client_workspaces")
    op.drop_index(op.f("ix_client_workspaces_workspace_status"), table_name="client_workspaces")
    op.drop_index(op.f("ix_client_workspaces_primary_contact_phone"), table_name="client_workspaces")
    op.drop_index(op.f("ix_client_workspaces_primary_contact_email"), table_name="client_workspaces")
    op.drop_index(op.f("ix_client_workspaces_source_booking_request_id"), table_name="client_workspaces")
    op.drop_table("client_workspaces")