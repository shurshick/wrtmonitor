"""Add client classification and activity history.

Revision ID: 0008_clients_and_devices
Revises: 0007_health_metrics
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "0008_clients_and_devices"
down_revision: str | None = "0007_health_metrics"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    client_columns = {
        column["name"] for column in inspector.get_columns("network_clients")
    }
    if "device_type" not in client_columns:
        op.add_column(
            "network_clients",
            sa.Column(
                "device_type",
                sa.String(length=24),
                nullable=False,
                server_default="unknown",
            ),
        )
    if "device_type_source" not in client_columns:
        op.add_column(
            "network_clients",
            sa.Column(
                "device_type_source",
                sa.String(length=16),
                nullable=False,
                server_default="automatic",
            ),
        )

    if not inspector.has_table("client_activity_events"):
        op.create_table(
            "client_activity_events",
            sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("client_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("state", sa.String(length=20), nullable=False),
            sa.Column("source", sa.String(length=40), nullable=True),
            sa.Column("ip_address", sa.String(length=45), nullable=True),
            sa.Column("interface", sa.String(length=80), nullable=True),
            sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(
                ["client_id"], ["network_clients.id"], ondelete="CASCADE"
            ),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            "ix_client_activity_client_occurred",
            "client_activity_events",
            ["client_id", sa.text("occurred_at DESC")],
        )
    else:
        activity_indexes = {
            index["name"] for index in inspector.get_indexes("client_activity_events")
        }
        if "ix_client_activity_client_occurred" not in activity_indexes:
            op.create_index(
                "ix_client_activity_client_occurred",
                "client_activity_events",
                ["client_id", sa.text("occurred_at DESC")],
            )


def downgrade() -> None:
    op.drop_index(
        "ix_client_activity_client_occurred", table_name="client_activity_events"
    )
    op.drop_table("client_activity_events")
    op.drop_column("network_clients", "device_type_source")
    op.drop_column("network_clients", "device_type")
