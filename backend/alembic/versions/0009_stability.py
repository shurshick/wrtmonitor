"""Add command idempotency and authentication attempt tracking."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0009_stability"
down_revision: str | None = "0008_client_presence"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("devices", sa.Column("previous_token_hash", sa.Text()))
    op.add_column(
        "devices", sa.Column("previous_token_expires_at", sa.DateTime(timezone=True))
    )
    op.add_column("devices", sa.Column("token_rollback_hash", sa.Text()))
    op.create_index(
        "ix_devices_previous_token_hash", "devices", ["previous_token_hash"]
    )
    op.add_column("device_commands", sa.Column("idempotency_key", sa.String(128)))
    op.create_index(
        "uq_device_commands_device_idempotency",
        "device_commands",
        ["device_id", "idempotency_key"],
        unique=True,
        postgresql_where=sa.text("idempotency_key IS NOT NULL"),
    )
    op.create_table(
        "auth_attempts",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("identity_hash", sa.Text(), nullable=False),
        sa.Column("ip_hash", sa.Text(), nullable=False),
        sa.Column("accepted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_auth_attempts_identity_created",
        "auth_attempts",
        ["identity_hash", "created_at"],
    )
    op.create_index(
        "ix_auth_attempts_ip_created",
        "auth_attempts",
        ["ip_hash", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_auth_attempts_ip_created", table_name="auth_attempts")
    op.drop_index("ix_auth_attempts_identity_created", table_name="auth_attempts")
    op.drop_table("auth_attempts")
    op.drop_index("uq_device_commands_device_idempotency", table_name="device_commands")
    op.drop_column("device_commands", "idempotency_key")
    op.drop_index("ix_devices_previous_token_hash", table_name="devices")
    op.drop_column("devices", "token_rollback_hash")
    op.drop_column("devices", "previous_token_expires_at")
    op.drop_column("devices", "previous_token_hash")
