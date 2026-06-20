"""Add lifecycle metadata to queued device commands."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0002_command_lifecycle"
down_revision: str | None = "0001_initial_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "device_commands",
        sa.Column("picked_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "device_commands",
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "device_commands",
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "device_commands",
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column("device_commands", sa.Column("last_error", sa.Text(), nullable=True))
    op.add_column(
        "device_commands",
        sa.Column("source", sa.String(length=40), nullable=False, server_default="api"),
    )
    op.execute(
        "UPDATE device_commands SET expires_at = created_at + interval '5 minutes' WHERE expires_at IS NULL"
    )
    op.alter_column("device_commands", "retry_count", server_default=None)
    op.alter_column("device_commands", "source", server_default=None)


def downgrade() -> None:
    op.drop_column("device_commands", "source")
    op.drop_column("device_commands", "last_error")
    op.drop_column("device_commands", "retry_count")
    op.drop_column("device_commands", "expires_at")
    op.drop_column("device_commands", "completed_at")
    op.drop_column("device_commands", "picked_at")
