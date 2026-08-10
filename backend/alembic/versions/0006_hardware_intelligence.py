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


def _column_names(table_name: str) -> set[str]:
    return {
        column["name"] for column in sa.inspect(op.get_bind()).get_columns(table_name)
    }


def _add_column_if_missing(table_name: str, column: sa.Column) -> None:
    if column.name not in _column_names(table_name):
        op.add_column(table_name, column)


def _drop_column_if_present(table_name: str, column_name: str) -> None:
    if column_name in _column_names(table_name):
        op.drop_column(table_name, column_name)


def upgrade() -> None:
    # The pre-release baseline is generated from current metadata. A clean database
    # can therefore already contain these columns before this incremental revision.
    _add_column_if_missing(
        "hardware_profiles",
        sa.Column(
            "origin", sa.String(length=40), nullable=False, server_default="builtin"
        ),
    )
    _add_column_if_missing(
        "hardware_profiles",
        sa.Column("verified", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    _add_column_if_missing(
        "hardware_profiles",
        sa.Column(
            "observation_count", sa.Integer(), nullable=False, server_default="0"
        ),
    )
    _add_column_if_missing(
        "hardware_profiles", sa.Column("first_seen_at", sa.DateTime(timezone=True))
    )
    _add_column_if_missing(
        "hardware_profiles", sa.Column("last_seen_at", sa.DateTime(timezone=True))
    )
    _add_column_if_missing(
        "hardware_sensor_samples", sa.Column("warning_milli_celsius", sa.Integer())
    )
    _add_column_if_missing(
        "hardware_sensor_samples", sa.Column("critical_milli_celsius", sa.Integer())
    )


def downgrade() -> None:
    _drop_column_if_present("hardware_sensor_samples", "critical_milli_celsius")
    _drop_column_if_present("hardware_sensor_samples", "warning_milli_celsius")
    _drop_column_if_present("hardware_profiles", "last_seen_at")
    _drop_column_if_present("hardware_profiles", "first_seen_at")
    _drop_column_if_present("hardware_profiles", "observation_count")
    _drop_column_if_present("hardware_profiles", "verified")
    _drop_column_if_present("hardware_profiles", "origin")
