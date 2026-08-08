"""Add durable terminal sessions and frame broker.

Revision ID: 0003_terminal_sessions
Revises: 0002_add_device_groups
Create Date: 2026-08-08 12:00:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0003_terminal_sessions"
down_revision: str | None = "0002_add_device_groups"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    connection = op.get_bind()
    inspector = sa.inspect(connection)

    if not inspector.has_table("terminal_sessions"):
        op.create_table(
            "terminal_sessions",
            sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("device_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("command_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("status", sa.String(length=24), nullable=False),
            sa.Column("columns", sa.Integer(), nullable=False),
            sa.Column("rows", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("last_activity_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("connected_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("close_reason", sa.Text(), nullable=True),
            sa.ForeignKeyConstraint(
                ["command_id"], ["device_commands.id"], ondelete="SET NULL"
            ),
            sa.ForeignKeyConstraint(["device_id"], ["devices.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
        )

    inspector = sa.inspect(connection)
    terminal_session_indexes = {
        item["name"] for item in inspector.get_indexes("terminal_sessions")
    }
    if "ix_terminal_sessions_device_status" not in terminal_session_indexes:
        op.create_index(
            "ix_terminal_sessions_device_status",
            "terminal_sessions",
            ["device_id", "status"],
        )

    if not inspector.has_table("terminal_frames"):
        op.create_table(
            "terminal_frames",
            sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
            sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("direction", sa.String(length=8), nullable=False),
            sa.Column("frame_type", sa.String(length=16), nullable=False),
            sa.Column("payload", sa.LargeBinary(), nullable=True),
            sa.Column(
                "frame_data",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
                server_default=sa.text("'{}'::jsonb"),
            ),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(
                ["session_id"], ["terminal_sessions.id"], ondelete="CASCADE"
            ),
            sa.PrimaryKeyConstraint("id"),
        )

    inspector = sa.inspect(connection)
    terminal_frame_indexes = {
        item["name"] for item in inspector.get_indexes("terminal_frames")
    }
    if "ix_terminal_frames_session_direction_id" not in terminal_frame_indexes:
        op.create_index(
            "ix_terminal_frames_session_direction_id",
            "terminal_frames",
            ["session_id", "direction", "id"],
        )


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if inspector.has_table("terminal_frames"):
        op.drop_table("terminal_frames")
    if inspector.has_table("terminal_sessions"):
        op.drop_table("terminal_sessions")
