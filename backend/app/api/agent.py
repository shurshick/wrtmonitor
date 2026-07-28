from datetime import UTC, datetime, timedelta
import secrets
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import Settings
from ..contracts import COMMAND_CONTRACT_VERSION
from ..db import get_db
from ..models import Device, DeviceCommand
from ..services.audit import audit
from ..services.auth import bearer_token, device_from_token, settings
from ..schemas import (
    AgentRegisterRequest,
    AgentTokenRollbackRequest,
    CommandResultRequest,
)
from ..security import hash_token
from ..services.commands import (
    TERMINAL_STATUSES,
    cleanup_device_command_history,
    expire_old_commands,
    requeue_stale_sent_commands,
)


router = APIRouter(prefix="/api/v1/agent")


@router.post("/token/rotate")
def rotate_device_token(
    authorization: str | None = Header(default=None), db: Session = Depends(get_db)
) -> dict[str, str | int]:
    device = device_from_token(authorization, db, for_update=True)
    new_token = secrets.token_urlsafe(32)
    rollback_token = secrets.token_urlsafe(32)
    device.previous_token_hash = device.token_hash
    device.previous_token_expires_at = datetime.now(UTC) + timedelta(minutes=10)
    device.token_rollback_hash = hash_token(rollback_token)
    device.token_hash = hash_token(new_token)
    device.updated_at = datetime.now(UTC)
    audit(db, None, "agent.token.rotate", "device", str(device.id))
    db.commit()
    return {
        "device_token": new_token,
        "rollback_token": rollback_token,
        "grace_seconds": 600,
    }


@router.post("/token/rollback")
def rollback_device_token(
    payload: AgentTokenRollbackRequest,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    previous_token_hash = hash_token(bearer_token(authorization))
    device = db.scalars(
        select(Device)
        .where(
            Device.previous_token_hash == previous_token_hash,
            Device.token_rollback_hash == hash_token(payload.rollback_token),
            Device.previous_token_expires_at > datetime.now(UTC),
            Device.archived_at.is_(None),
        )
        .with_for_update()
    ).first()
    if device is None:
        raise HTTPException(status_code=401, detail="Token rollback is not available")
    device.token_hash = previous_token_hash
    device.previous_token_hash = None
    device.previous_token_expires_at = None
    device.token_rollback_hash = None
    device.updated_at = datetime.now(UTC)
    audit(db, None, "agent.token.rollback", "device", str(device.id))
    db.commit()
    return {"status": "rolled_back"}


@router.post("/token/confirm")
def confirm_device_token(
    authorization: str | None = Header(default=None), db: Session = Depends(get_db)
) -> dict[str, str]:
    provided_hash = hash_token(bearer_token(authorization))
    device = device_from_token(authorization, db, for_update=True)
    if device.token_hash != provided_hash:
        raise HTTPException(status_code=409, detail="Current device token required")
    device.previous_token_hash = None
    device.previous_token_expires_at = None
    device.token_rollback_hash = None
    device.updated_at = datetime.now(UTC)
    audit(db, None, "agent.token.confirm", "device", str(device.id))
    db.commit()
    return {"status": "confirmed"}


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
        .with_for_update(skip_locked=True)
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
            "contract_version": COMMAND_CONTRACT_VERSION,
        }
        for command in commands
    ]


@router.post("/commands/{command_id}/result")
def command_result(
    command_id: UUID,
    payload: CommandResultRequest,
    authorization: str | None = Header(default=None),
    config: Settings = Depends(settings),
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
        error_detail = payload.result.get("error_detail")
        if isinstance(error_detail, dict):
            error_code = str(error_detail.get("code") or "command_failed")
            error_message = str(error_detail.get("message") or "Command failed")
            command.last_error = f"{error_code}: {error_message}"
        else:
            command.last_error = (
                str(payload.result.get("error"))
                if payload.result.get("error")
                else None
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
    if command.status in TERMINAL_STATUSES:
        cleanup_device_command_history(
            db,
            device.id,
            config.command_history_retention_days,
            config.command_history_max_per_device,
        )
    db.commit()
    return {"status": command.status}
