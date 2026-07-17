"""Add persistent client registry, policies and traffic samples."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "0004_client_registry"
down_revision: str | None = "0003_device_archive"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "client_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "device_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("devices.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("policy", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("device_id", "name", name="uq_client_profiles_device_name"),
    )
    op.create_table(
        "network_clients",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "device_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("devices.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "profile_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("client_profiles.id", ondelete="SET NULL"),
        ),
        sa.Column("mac", sa.String(17), nullable=False),
        sa.Column("display_name", sa.String(120)),
        sa.Column("vendor", sa.String(160)),
        sa.Column("hostname", sa.String(120)),
        sa.Column("ip_address", sa.String(45)),
        sa.Column("interface", sa.String(80)),
        sa.Column("online", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_static", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("policy", postgresql.JSONB(), nullable=False),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("device_id", "mac", name="uq_network_clients_device_mac"),
    )
    op.create_index(
        "ix_network_clients_device_online", "network_clients", ["device_id", "online"]
    )
    op.create_table(
        "client_traffic_samples",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "client_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("network_clients.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("rx_bytes", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("tx_bytes", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_client_traffic_client_created",
        "client_traffic_samples",
        ["client_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_table("client_traffic_samples")
    op.drop_table("network_clients")
    op.drop_table("client_profiles")
