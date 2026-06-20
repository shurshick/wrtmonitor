from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from ..models import AuditLog


def audit(
    db: Session,
    user_id: UUID | None,
    action: str,
    object_type: str | None = None,
    object_id: str | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    db.add(
        AuditLog(
            id=uuid4(),
            user_id=user_id,
            action=action,
            object_type=object_type,
            object_id=object_id,
            details=details,
            created_at=datetime.now(UTC),
        )
    )
