"""Add hardware learning metadata and observed thermal limits.

Revision ID: 0006_hardware_intelligence
Revises: 0005_hardware_catalog
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0006_hardware_intelligence"
down_revision: str | None = "0005_hardware_catalog"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "hardware_profiles",
        sa.Column(
            "origin", sa.String(length=40), nullable=False, server_default="builtin"
        ),
    )
    op.add_column(
        "hardware_profiles",
        sa.Column("verified", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "hardware_profiles",
        sa.Column(
            "observation_count", sa.Integer(), nullable=False, server_default="0"
        ),
    )
    op.add_column(
        "hardware_profiles", sa.Column("first_seen_at", sa.DateTime(timezone=True))
    )
    op.add_column(
        "hardware_profiles", sa.Column("last_seen_at", sa.DateTime(timezone=True))
    )
    op.add_column(
        "hardware_sensor_samples", sa.Column("warning_milli_celsius", sa.Integer())
    )
    op.add_column(
        "hardware_sensor_samples", sa.Column("critical_milli_celsius", sa.Integer())
    )


def downgrade() -> None:
    op.drop_column("hardware_sensor_samples", "critical_milli_celsius")
    op.drop_column("hardware_sensor_samples", "warning_milli_celsius")
    op.drop_column("hardware_profiles", "last_seen_at")
    op.drop_column("hardware_profiles", "first_seen_at")
    op.drop_column("hardware_profiles", "observation_count")
    op.drop_column("hardware_profiles", "verified")
    op.drop_column("hardware_profiles", "origin")
