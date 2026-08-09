"""Add persistent events, notifications and safe automations.

Revision ID: 0004_events_automation
Revises: 0003_terminal_sessions
"""

from collections.abc import Sequence

from alembic import op

from backend.app import models  # noqa: F401
from backend.app.db import Base


revision: str = "0004_events_automation"
down_revision: str | None = "0003_terminal_sessions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


TABLES = ("event_records", "notification_rules", "automation_rules", "automation_runs")


def upgrade() -> None:
    Base.metadata.create_all(
        bind=op.get_bind(), tables=[Base.metadata.tables[name] for name in TABLES]
    )


def downgrade() -> None:
    for name in reversed(TABLES):
        op.drop_table(name)
