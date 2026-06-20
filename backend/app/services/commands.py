from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import update
from sqlalchemy.orm import Session

from ..models import DeviceCommand


COMMAND_TTL = timedelta(minutes=5)
TERMINAL_STATUSES = {"success", "failed", "expired", "cancelled"}
ALLOWED_COMMANDS = {
    "router.reboot",
    "wifi.status",
    "wifi.set_enabled",
    "wifi.set_ssid",
    "network.interfaces",
}


def build_command_payload_from_web_form(
    command_type: str, ssid: str, enabled: str
) -> dict:
    if command_type not in ALLOWED_COMMANDS:
        raise ValueError("Unsupported command")
    if command_type == "wifi.set_ssid":
        if not ssid.strip():
            raise ValueError("SSID is required")
        return {"ssid": ssid.strip()}
    if command_type == "wifi.set_enabled":
        return {"enabled": enabled.lower() == "true"}
    return {}


def now_utc() -> datetime:
    return datetime.now(UTC)


def create_device_command(
    db: Session,
    *,
    device_id: UUID,
    command_type: str,
    payload: dict,
    created_by: UUID | None,
    source: str,
) -> DeviceCommand:
    now = now_utc()
    command = DeviceCommand(
        id=uuid4(),
        device_id=device_id,
        command_type=command_type,
        payload=payload,
        status="queued",
        result=None,
        created_by=created_by,
        created_at=now,
        updated_at=now,
        expires_at=now + COMMAND_TTL,
        retry_count=0,
        source=source,
    )
    db.add(command)
    return command


def expire_old_commands(db: Session) -> int:
    result = db.execute(
        update(DeviceCommand)
        .where(
            DeviceCommand.status.in_(("queued", "sent", "running")),
            DeviceCommand.expires_at.is_not(None),
            DeviceCommand.expires_at < now_utc(),
        )
        .values(
            status="expired",
            updated_at=now_utc(),
            completed_at=now_utc(),
            last_error="Command expired",
        )
    )
    return int(result.rowcount or 0)
