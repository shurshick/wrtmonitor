from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import DeviceCommand, User
from ..services.audit import audit
from ..services.auth import current_user
from ..services.devices import get_user_device_or_404
from ..schemas import CommandCreateRequest
from ..services.commands import (
    ALLOWED_COMMANDS,
    create_device_command,
    expire_old_commands,
)


router = APIRouter(prefix="/api/v1/devices")


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
    command = create_device_command(
        db,
        device_id=device_id,
        command_type=payload.command_type,
        payload=payload.payload,
        created_by=user.id,
        source="api",
    )
    audit(
        db,
        user.id,
        "command.create",
        "device_command",
        str(command.id),
        {"command_type": payload.command_type},
    )
    db.commit()
    return {"command_id": str(command.id), "status": command.status}


@router.get("/{device_id}/commands")
def list_device_commands(
    device_id: UUID,
    limit: int = 20,
    status: str | None = None,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    get_user_device_or_404(db, user, device_id)
    expire_old_commands(db)
    query = select(DeviceCommand).where(DeviceCommand.device_id == device_id)
    if status:
        query = query.where(DeviceCommand.status == status)
    commands = db.scalars(
        query.order_by(DeviceCommand.created_at.desc()).limit(min(max(limit, 1), 100))
    ).all()
    db.commit()

    def iso(value):
        return value.isoformat() if value else None

    return [
        {
            "id": str(command.id),
            "command_type": command.command_type,
            "status": command.status,
            "source": command.source,
            "payload": command.payload,
            "result": command.result,
            "created_at": iso(command.created_at),
            "picked_at": iso(command.picked_at),
            "completed_at": iso(command.completed_at),
            "expires_at": iso(command.expires_at),
            "last_error": command.last_error,
        }
        for command in commands
    ]
