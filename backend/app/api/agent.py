from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Device, DeviceCommand
from ..services.audit import audit
from ..services.auth import device_from_token
from ..schemas import AgentRegisterRequest, CommandResultRequest
from ..security import hash_token
from ..services.commands import (
    TERMINAL_STATUSES,
    expire_old_commands,
    requeue_stale_sent_commands,
)


router = APIRouter(prefix="/api/v1/agent")


@router.post("/register")
def register_agent(
    payload: AgentRegisterRequest, db: Session = Depends(get_db)
) -> dict[str, str]:
    existing = db.scalars(
        select(Device).where(
            Device.token_hash == hash_token(payload.device_token),
            Device.archived_at.is_(None),
        )
    ).first()
    if existing:
        return {"device_id": str(existing.id)}
    raise HTTPException(status_code=401, detail="Unknown device token")


@router.get("/commands")
def poll_commands(
    authorization: str | None = Header(default=None), db: Session = Depends(get_db)
) -> list[dict]:
    device = device_from_token(authorization, db)
    expire_old_commands(db)
    requeue_stale_sent_commands(db)
    commands = db.scalars(
        select(DeviceCommand)
        .where(DeviceCommand.device_id == device.id, DeviceCommand.status == "queued")
        .order_by(DeviceCommand.created_at.asc())
        .limit(5)
    ).all()
    now = datetime.now(UTC)
    for command in commands:
        command.status, command.updated_at, command.picked_at, command.retry_count = (
            "sent",
            now,
            now,
            command.retry_count + 1,
        )
    db.commit()
    return [
        {
            "id": str(command.id),
            "type": command.command_type,
            "payload": command.payload,
        }
        for command in commands
    ]


@router.post("/commands/{command_id}/result")
def command_result(
    command_id: UUID,
    payload: CommandResultRequest,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    device = device_from_token(authorization, db)
    command = db.get(DeviceCommand, command_id)
    if not command or command.device_id != device.id:
        raise HTTPException(status_code=404, detail="Command not found")
    if command.status in TERMINAL_STATUSES:
        return {"status": command.status}
    now = datetime.now(UTC)
    if payload.status == "running":
        if command.status not in {"sent", "running"}:
            raise HTTPException(status_code=409, detail="Command cannot start")
        command.status = "running"
        command.updated_at = now
        command.result = payload.result or None
        command.last_error = None
    elif payload.status in {"done", "success", "failed"}:
        command.status = (
            "success" if payload.status in {"done", "success"} else "failed"
        )
        command.result, command.updated_at, command.completed_at = (
            payload.result,
            now,
            now,
        )
        command.last_error = (
            str(payload.result.get("error")) if payload.result.get("error") else None
        )
    else:
        raise HTTPException(status_code=422, detail="Unsupported command status")
    if command.command_type == "agent.disconnect" and command.status == "success":
        device.status = "disabled"
        device.updated_at = now
    if (
        command.command_type == "wifi.set_password"
        and command.status in TERMINAL_STATUSES
    ):
        command.payload = {}
    audit(
        db,
        None,
        "command.result",
        "device_command",
        str(command.id),
        {"status": command.status},
    )
    db.commit()
    return {"status": command.status}
