from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Device, DeviceTelemetry, User


LEGACY_AGENT_CAPABILITIES = {
    "agent.rollback",
    "agent.update",
    "network.read",
    "system.reboot",
    "wifi.disable",
    "wifi.enable",
    "wifi.set_password",
    "wifi.set_ssid",
}


def get_device_or_404(db: Session, device_id: UUID) -> Device:
    device = db.scalars(
        select(Device).where(Device.id == device_id, Device.archived_at.is_(None))
    ).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    return device


def get_user_device_or_404(db: Session, user: User, device_id: UUID) -> Device:
    # Current deployment model is single-owner. Keeping the user parameter here
    # prevents future multi-user routes from accidentally bypassing ownership.
    del user
    return get_device_or_404(db, device_id)


def archive_device_or_409(device: Device) -> None:
    if device.status != "disabled":
        raise HTTPException(
            status_code=409,
            detail="Only disabled devices can be removed from the active list",
        )


def latest_device_telemetry(db: Session, device_id: UUID) -> DeviceTelemetry | None:
    return db.scalars(
        select(DeviceTelemetry)
        .where(DeviceTelemetry.device_id == device_id)
        .order_by(DeviceTelemetry.created_at.desc())
        .limit(1)
    ).first()


def get_latest_agent_status(db: Session, device_id: UUID) -> dict:
    telemetry = latest_device_telemetry(db, device_id)
    payload = telemetry.payload if telemetry else {}
    return dict((payload.get("agent") or {}))


def get_latest_agent_capabilities(db: Session, device_id: UUID) -> dict[str, bool]:
    agent = get_latest_agent_status(db, device_id)
    capabilities = agent.get("capabilities") or {}
    if not isinstance(capabilities, dict):
        return {}
    return {str(key): bool(value) for key, value in capabilities.items()}


def device_supports(db: Session, device_id: UUID, capability: str) -> bool:
    capabilities = get_latest_agent_capabilities(db, device_id)
    if not capabilities:
        return capability in LEGACY_AGENT_CAPABILITIES
    return bool(capabilities.get(capability, False))
