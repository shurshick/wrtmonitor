"""Frozen pre-release baseline as shipped in 0.55.2.

Future model changes belong in new revisions, never in this snapshot.
Existing versioned databases do not replay this revision.
"""

from collections.abc import Sequence
import json
from pathlib import Path

from alembic import op

revision: str = "0001_initial_schema"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    snapshot = json.loads(Path(__file__).with_name("0001_schema.json").read_text())
    for statement in snapshot["statements"]:
        op.execute(statement)


def downgrade() -> None:
    snapshot = json.loads(Path(__file__).with_name("0001_schema.json").read_text())
    for table in reversed(snapshot["tables"]):
        op.drop_table(table, if_exists=True)
