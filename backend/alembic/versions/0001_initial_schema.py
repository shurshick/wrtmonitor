"""Single pre-release schema baseline.

Before the first public release WrtMonitor intentionally supports clean installs only.
The baseline is generated from the same SQLAlchemy metadata used by the application,
so a new database cannot drift from the runtime model.
"""

from collections.abc import Sequence

from alembic import op

from backend.app.db import Base
from backend.app import models  # noqa: F401


revision: str = "0001_initial_schema"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    Base.metadata.create_all(bind=op.get_bind(), checkfirst=False)


def downgrade() -> None:
    Base.metadata.drop_all(bind=op.get_bind(), checkfirst=False)
