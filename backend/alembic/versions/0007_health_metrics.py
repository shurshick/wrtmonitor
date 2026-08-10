"""Add temperature and storage history metrics.

Revision ID: 0007_health_metrics
Revises: 0006_hardware_intelligence
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0007_health_metrics"
down_revision: str | None = "0006_hardware_intelligence"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _column_names() -> set[str]:
    return {
        column["name"]
        for column in sa.inspect(op.get_bind()).get_columns("device_telemetry_metrics")
    }


def upgrade() -> None:
    columns = _column_names()
    if "temperature_celsius" not in columns:
        op.add_column(
            "device_telemetry_metrics", sa.Column("temperature_celsius", sa.Float())
        )
    if "storage_percent" not in columns:
        op.add_column(
            "device_telemetry_metrics", sa.Column("storage_percent", sa.Float())
        )


def downgrade() -> None:
    columns = _column_names()
    if "storage_percent" in columns:
        op.drop_column("device_telemetry_metrics", "storage_percent")
    if "temperature_celsius" in columns:
        op.drop_column("device_telemetry_metrics", "temperature_celsius")
