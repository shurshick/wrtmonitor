from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from ..config import APP_VERSION
from ..models import DeviceCommand
from .commands import create_device_command
from .agent_versions import version_key


def agent_update_required(installed: str, available: str = APP_VERSION) -> bool:
    installed_key = version_key(installed)
    available_key = version_key(available)
    return bool(
        installed_key is not None
        and available_key is not None
        and installed_key < available_key
    )


def queue_automatic_agent_update(
    db: Session,
    *,
    device_id: UUID,
    telemetry: dict[str, Any],
    now: datetime,
) -> DeviceCommand | None:
    agent = telemetry.get("agent") or {}
    installed = str(agent.get("version") or "").strip()
    if not agent.get("auto_update_enabled", False):
        return None
    if not agent_update_required(installed):
        return None
    return create_device_command(
        db,
        device_id=device_id,
        command_type="agent.update",
        payload={},
        created_by=None,
        source="auto-update",
        idempotency_key=f"agent-auto-update:{APP_VERSION}:{now:%Y%m%d%H}",
    )
