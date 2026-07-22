"""Add expiring client presence evidence."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0008_client_presence"
down_revision: str | None = "0007_mobile_pairing"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "network_clients",
        sa.Column(
            "presence_state",
            sa.String(20),
            nullable=False,
            server_default="offline",
        ),
    )
    op.add_column("network_clients", sa.Column("presence_source", sa.String(40)))
    op.add_column(
        "network_clients", sa.Column("last_observed_at", sa.DateTime(timezone=True))
    )
    op.add_column(
        "network_clients", sa.Column("last_confirmed_at", sa.DateTime(timezone=True))
    )
    op.add_column(
        "network_clients", sa.Column("online_until", sa.DateTime(timezone=True))
    )
    op.add_column(
        "network_clients",
        sa.Column("presence_expires_at", sa.DateTime(timezone=True)),
    )
    op.execute("UPDATE network_clients SET online = false, presence_state = 'offline'")
    op.create_index(
        "ix_network_clients_device_presence",
        "network_clients",
        ["device_id", "presence_state"],
    )


def downgrade() -> None:
    op.drop_index("ix_network_clients_device_presence", table_name="network_clients")
    op.drop_column("network_clients", "presence_expires_at")
    op.drop_column("network_clients", "online_until")
    op.drop_column("network_clients", "last_confirmed_at")
    op.drop_column("network_clients", "last_observed_at")
    op.drop_column("network_clients", "presence_source")
    op.drop_column("network_clients", "presence_state")
