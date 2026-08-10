"""Add hardware catalog, observed identities and temperature samples.

Revision ID: 0005_hardware_catalog
Revises: 0004_events_automation
"""

from collections.abc import Sequence

from alembic import op

from backend.app import models  # noqa: F401
from backend.app.db import Base


revision: str = "0005_hardware_catalog"
down_revision: str | None = "0004_events_automation"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLES = (
    "hardware_profiles",
    "device_hardware_identities",
    "hardware_sensor_samples",
)


def upgrade() -> None:
    Base.metadata.create_all(
        bind=op.get_bind(), tables=[Base.metadata.tables[name] for name in TABLES]
    )


def downgrade() -> None:
    for name in reversed(TABLES):
        op.drop_table(name)
