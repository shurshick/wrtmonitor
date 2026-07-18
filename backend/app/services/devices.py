from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ..models import (
    AuditLog,
    Device,
    DeviceCommand,
    DeviceTelemetry,
    DeviceTelemetryMetric,
    User,
)
from .auth import ensure_single_owner_access


def get_device_or_404(db: Session, device_id: UUID) -> Device:
    device = db.scalars(
        select(Device).where(Device.id == device_id, Device.archived_at.is_(None))
    ).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    return device


def get_user_device_or_404(db: Session, user: User, device_id: UUID) -> Device:
    ensure_single_owner_access(user)
    return get_device_or_404(db, device_id)


def delete_device_permanently(db: Session, device: Device) -> None:
    """Delete a router and every database record owned by it."""
    device_id = device.id
    command_ids = list(
        db.scalars(
            select(DeviceCommand.id).where(DeviceCommand.device_id == device_id)
        ).all()
    )
    db.execute(
        delete(AuditLog).where(
            AuditLog.object_type == "device", AuditLog.object_id == str(device_id)
        )
    )
    if command_ids:
        db.execute(
            delete(AuditLog).where(
                AuditLog.object_type == "device_command",
                AuditLog.object_id.in_([str(command_id) for command_id in command_ids]),
            )
        )
    db.execute(delete(DeviceTelemetry).where(DeviceTelemetry.device_id == device_id))
    db.execute(
        delete(DeviceTelemetryMetric).where(
            DeviceTelemetryMetric.device_id == device_id
        )
    )
    db.execute(delete(DeviceCommand).where(DeviceCommand.device_id == device_id))
    db.delete(device)


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
        return False
    return bool(capabilities.get(capability, False))
