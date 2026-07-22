"""Add one-time mobile pairing tokens."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "0007_mobile_pairing"
down_revision: str | None = "0006_telemetry_metrics"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "user_sessions",
        sa.Column(
            "client_type",
            sa.String(40),
            nullable=False,
            server_default="password",
        ),
    )
    op.create_table(
        "mobile_pairing_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("token_hash", sa.Text(), nullable=False, unique=True),
        sa.Column("server_url", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True)),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column(
            "used_session_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("user_sessions.id", ondelete="SET NULL"),
        ),
    )
    op.create_index(
        "ix_mobile_pairing_tokens_user_created",
        "mobile_pairing_tokens",
        ["user_id", sa.text("created_at DESC")],
    )
    op.create_table(
        "mobile_pairing_attempts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("identity_hash", sa.Text(), nullable=False),
        sa.Column("token_hash", sa.Text(), nullable=False),
        sa.Column("accepted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_mobile_pairing_attempts_identity_created",
        "mobile_pairing_attempts",
        ["identity_hash", sa.text("created_at DESC")],
    )
    op.create_index(
        "ix_mobile_pairing_attempts_token_created",
        "mobile_pairing_attempts",
        ["token_hash", sa.text("created_at DESC")],
    )
    op.create_index(
        "ix_mobile_pairing_attempts_created",
        "mobile_pairing_attempts",
        ["created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_mobile_pairing_attempts_created",
        table_name="mobile_pairing_attempts",
    )
    op.drop_index(
        "ix_mobile_pairing_attempts_token_created",
        table_name="mobile_pairing_attempts",
    )
    op.drop_index(
        "ix_mobile_pairing_attempts_identity_created",
        table_name="mobile_pairing_attempts",
    )
    op.drop_table("mobile_pairing_attempts")
    op.drop_index(
        "ix_mobile_pairing_tokens_user_created",
        table_name="mobile_pairing_tokens",
    )
    op.drop_table("mobile_pairing_tokens")
    op.drop_column("user_sessions", "client_type")
