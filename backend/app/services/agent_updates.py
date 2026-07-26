import re
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from ..config import APP_VERSION
from ..models import DeviceCommand
from .commands import create_device_command


_SEMVER = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)(?:-rc(\d+))?(?:\+.*)?$")


def _version_key(value: str) -> tuple[int, int, int, int, int] | None:
    match = _SEMVER.fullmatch(value.strip())
    if match is None:
        return None
    major, minor, patch, rc = match.groups()
    return (
        int(major),
        int(minor),
        int(patch),
        1 if rc is None else 0,
        int(rc or 0),
    )


def agent_update_required(installed: str, available: str = APP_VERSION) -> bool:
    installed_key = _version_key(installed)
    available_key = _version_key(available)
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
