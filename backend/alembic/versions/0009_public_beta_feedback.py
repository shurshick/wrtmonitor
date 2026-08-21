"""Add public beta feedback records.

Revision ID: 0009_public_beta_feedback
Revises: 0008_clients_and_devices
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "0009_public_beta_feedback"
down_revision: str | None = "0008_clients_and_devices"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if inspector.has_table("feedback_records"):
        return
    op.create_table(
        "feedback_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("device_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("source", sa.String(length=24), nullable=False),
        sa.Column("category", sa.String(length=24), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("app_version", sa.String(length=40), nullable=True),
        sa.Column(
            "client_context",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="new"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["device_id"], ["devices.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_feedback_records_created", "feedback_records", [sa.text("created_at DESC")]
    )
    op.create_index(
        "ix_feedback_records_status_created",
        "feedback_records",
        ["status", sa.text("created_at DESC")],
    )


def downgrade() -> None:
    op.drop_index("ix_feedback_records_status_created", table_name="feedback_records")
    op.drop_index("ix_feedback_records_created", table_name="feedback_records")
    op.drop_table("feedback_records")
