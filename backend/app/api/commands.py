from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import Settings
from ..db import get_db
from ..models import DeviceCommand, User
from ..services.audit import audit
from ..services.auth import current_user, settings
from ..services.devices import (
    device_supports,
    get_user_device_or_404,
    latest_device_telemetry,
)
from ..schemas import CommandCreateRequest
from ..services.commands import (
    ALLOWED_COMMANDS,
    cleanup_device_command_history,
    command_history_entry,
    create_device_command,
    expire_old_commands,
    validate_command_request,
)
from ..services.config_transactions import build_command_preview, ensure_preflight_valid


router = APIRouter(prefix="/api/v1/devices")


@router.post("/{device_id}/commands/preview")
def preview_command(
    device_id: UUID,
    payload: CommandCreateRequest,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    get_user_device_or_404(db, user, device_id)
    normalized_payload = validate_command_request(
        command_type=payload.command_type,
        payload=payload.payload,
        confirmed=True,
        device_supports=lambda capability: device_supports(db, device_id, capability),
    )
    telemetry = latest_device_telemetry(db, device_id)
    return build_command_preview(
        payload.command_type,
        normalized_payload,
        telemetry.payload if telemetry else {},
    )


@router.post("/{device_id}/commands")
def create_command(
    device_id: UUID,
    payload: CommandCreateRequest,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    if payload.command_type not in ALLOWED_COMMANDS:
        raise HTTPException(status_code=400, detail="Command is not allowed")
    get_user_device_or_404(db, user, device_id)
    normalized_payload = validate_command_request(
        command_type=payload.command_type,
        payload=payload.payload,
        confirmed=payload.confirmed,
        device_supports=lambda capability: device_supports(db, device_id, capability),
    )
    telemetry = latest_device_telemetry(db, device_id)
    ensure_preflight_valid(
        payload.command_type,
        normalized_payload,
        telemetry.payload if telemetry else {},
    )
    command = create_device_command(
        db,
        device_id=device_id,
        command_type=payload.command_type,
        payload=normalized_payload,
        created_by=user.id,
        source="api",
    )
    audit(
        db,
        user.id,
        "command.create",
        "device_command",
        str(command.id),
        {"command_type": payload.command_type, "confirmed": payload.confirmed},
    )
    db.commit()
    return {"command_id": str(command.id), "status": command.status}


@router.post("/{device_id}/disconnect")
def disconnect_device(
    device_id: UUID,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    device = get_user_device_or_404(db, user, device_id)
    if device.status in {"disabled", "disconnecting"}:
        return {"status": device.status}
    command = create_device_command(
        db,
        device_id=device.id,
        command_type="agent.disconnect",
        payload={},
        created_by=user.id,
        source="api",
    )
    device.status = "disconnecting"
    device.updated_at = datetime.now(UTC)
    audit(
        db,
        user.id,
        "device.disconnect",
        "device",
        str(device.id),
        {"command_id": str(command.id)},
    )
    db.commit()
    return {"command_id": str(command.id), "status": "disconnecting"}


@router.get("/{device_id}/commands")
def list_device_commands(
    device_id: UUID,
    limit: int = 20,
    offset: int = 0,
    status: str | None = None,
    user: User = Depends(current_user),
    config: Settings = Depends(settings),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    get_user_device_or_404(db, user, device_id)
    expire_old_commands(db)
    cleanup_device_command_history(
        db,
        device_id,
        config.command_history_retention_days,
        config.command_history_max_per_device,
    )
    query = select(DeviceCommand).where(DeviceCommand.device_id == device_id)
    if status:
        query = query.where(DeviceCommand.status == status)
    commands = db.scalars(
        query.order_by(DeviceCommand.created_at.desc())
        .offset(max(offset, 0))
        .limit(min(max(limit, 1), 100))
    ).all()
    db.commit()

    return [command_history_entry(command) for command in commands]
