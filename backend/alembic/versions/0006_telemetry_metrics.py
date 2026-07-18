"""Add compact long-term telemetry metrics."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "0006_telemetry_metrics"
down_revision: str | None = "0005_user_sessions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "device_telemetry_metrics",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "device_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("devices.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("rx_bps", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("tx_bps", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("rx_bytes", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("tx_bytes", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("load_1m", sa.Float(), nullable=False, server_default="0"),
        sa.Column("memory_percent", sa.Float(), nullable=False, server_default="0"),
        sa.Column("client_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "interfaces", postgresql.JSONB(), nullable=False, server_default="{}"
        ),
        sa.Column("wifi", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_device_telemetry_metrics_device_created",
        "device_telemetry_metrics",
        ["device_id", sa.text("created_at DESC")],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_device_telemetry_metrics_device_created",
        table_name="device_telemetry_metrics",
    )
    op.drop_table("device_telemetry_metrics")
