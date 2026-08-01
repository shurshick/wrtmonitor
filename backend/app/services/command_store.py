from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any, Callable
from uuid import UUID, uuid4

from fastapi import HTTPException
from sqlalchemy import and_, delete, or_, select, update
from sqlalchemy.orm import Session

from ..models import DeviceCommand, DeviceTelemetry
from .command_common import (
    COMMAND_DELIVERY_LEASE,
    TERMINAL_STATUSES,
    get_command_metadata,
    _require_confirmation,
)
from .command_errors import public_command_error
from .command_registry import COMMAND_REGISTRY
from .command_validation import validate_command_payload
from .config_transactions import (
    attach_transaction_metadata,
    ensure_preflight_valid,
    is_transactional_command,
)


def mask_secrets(value: Any, secret_fields: set[str]) -> Any:
    if isinstance(value, dict):
        return {
            key: (
                "********"
                if key in secret_fields
                else mask_secrets(item, secret_fields)
            )
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [mask_secrets(item, secret_fields) for item in value]
    return value


def public_command_payload(command_type: str, payload: dict | None) -> dict:
    metadata = COMMAND_REGISTRY.get(command_type, {})
    secret_fields = set(metadata.get("secret_fields", []))
    safe_payload = dict(payload or {})
    return mask_secrets(safe_payload, secret_fields)


def public_command_result(
    command_type: str, result: dict[str, Any] | None
) -> dict[str, Any] | None:
    if result is None:
        return None
    metadata = COMMAND_REGISTRY.get(command_type, {})
    secret_fields = set(metadata.get("secret_fields", []))
    safe_result = mask_secrets(result, secret_fields)
    for field in ("archive_base64", "bundle_base64"):
        if field in safe_result:
            safe_result[field] = "download available"
    return safe_result


def command_history_entry(command: DeviceCommand) -> dict[str, Any]:
    metadata = COMMAND_REGISTRY.get(command.command_type, {})

    def iso(value: datetime | None) -> str | None:
        return value.isoformat() if value else None

    return {
        "id": str(command.id),
        "command_type": command.command_type,
        "status": command.status,
        "source": command.source,
        "payload": public_command_payload(command.command_type, command.payload),
        "result": public_command_result(command.command_type, command.result),
        "created_at": iso(command.created_at),
        "picked_at": iso(command.picked_at),
        "completed_at": iso(command.completed_at),
        "expires_at": iso(command.expires_at),
        "retry_count": command.retry_count,
        "last_error": command.last_error,
        "error": public_command_error(command.result),
        "risk_level": metadata.get("risk_level"),
        "capability": metadata.get("capability"),
        "reliability": metadata.get("reliability"),
    }


def now_utc() -> datetime:
    return datetime.now(UTC)


def create_device_command(
    db: Session,
    *,
    device_id: UUID,
    command_type: str,
    payload: dict[str, Any],
    created_by: UUID | None,
    source: str,
    idempotency_key: str | None = None,
) -> DeviceCommand:
    now = now_utc()
    metadata = get_command_metadata(command_type)
    if idempotency_key:
        existing = db.scalars(
            select(DeviceCommand).where(
                DeviceCommand.device_id == device_id,
                DeviceCommand.idempotency_key == idempotency_key,
            )
        ).first()
        if existing:
            if existing.command_type != command_type:
                raise HTTPException(
                    status_code=409,
                    detail="Idempotency key is already used by another command type",
                )
            return existing
    command_id = uuid4()
    if command_type == "agent.update":
        latest = db.scalars(
            select(DeviceTelemetry)
            .where(DeviceTelemetry.device_id == device_id)
            .order_by(DeviceTelemetry.created_at.desc())
            .limit(1)
        ).first()
        installed = (
            str(((latest.payload.get("agent") or {}).get("version") or ""))
            if latest
            else ""
        )
        if installed == "0.9.0":
            payload = {**payload, "allow_downgrade": True}
    command = DeviceCommand(
        id=command_id,
        device_id=device_id,
        command_type=command_type,
        payload=attach_transaction_metadata(command_type, payload, command_id),
        status="queued",
        result=None,
        created_by=created_by,
        created_at=now,
        updated_at=now,
        expires_at=now
        + timedelta(
            seconds=int(metadata["reliability"]["delivery"]["timeout_seconds"])
        ),
        retry_count=0,
        source=source,
        idempotency_key=idempotency_key,
    )
    db.add(command)
    return command


def validate_command_request(
    *,
    command_type: str,
    payload: dict[str, Any] | None,
    confirmed: bool,
    device_supports: Callable[[str], bool] | None = None,
) -> dict[str, Any]:
    metadata = get_command_metadata(command_type)
    _require_confirmation(command_type, confirmed)
    normalized_payload = validate_command_payload(command_type, payload or {})
    ensure_preflight_valid(command_type, normalized_payload)
    if (
        is_transactional_command(command_type)
        and device_supports is not None
        and not device_supports("config.transaction")
    ):
        raise HTTPException(
            status_code=409,
            detail="Agent update required: safe configuration transactions are unavailable",
        )
    capability = metadata.get("capability")
    if capability and device_supports is not None and not device_supports(capability):
        raise HTTPException(
            status_code=409,
            detail=f"Device does not support capability '{capability}'",
        )
    return normalized_payload


def expire_old_commands(db: Session) -> int:
    timestamp = now_utc()
    result = db.execute(
        update(DeviceCommand)
        .where(
            DeviceCommand.status.in_(("queued", "sent", "running")),
            DeviceCommand.expires_at.is_not(None),
            DeviceCommand.expires_at < timestamp,
        )
        .values(
            status="expired",
            updated_at=timestamp,
            completed_at=timestamp,
            last_error="Command expired",
        )
    )
    return int(result.rowcount or 0)


def cleanup_device_command_history(
    db: Session,
    device_id: UUID,
    retention_days: int,
    max_per_device: int,
) -> int:
    """Remove old terminal commands without touching active lifecycle records."""
    cutoff = now_utc() - timedelta(days=max(1, retention_days))
    terminal_statuses = tuple(TERMINAL_STATUSES)
    removed_by_age = db.execute(
        delete(DeviceCommand).where(
            DeviceCommand.device_id == device_id,
            DeviceCommand.status.in_(terminal_statuses),
            or_(
                DeviceCommand.completed_at < cutoff,
                and_(
                    DeviceCommand.completed_at.is_(None),
                    DeviceCommand.updated_at < cutoff,
                ),
            ),
        )
    )
    overflow_ids = (
        select(DeviceCommand.id)
        .where(
            DeviceCommand.device_id == device_id,
            DeviceCommand.status.in_(terminal_statuses),
        )
        .order_by(DeviceCommand.created_at.desc(), DeviceCommand.id.desc())
        .offset(max(10, max_per_device))
    )
    removed_overflow = db.execute(
        delete(DeviceCommand).where(DeviceCommand.id.in_(overflow_ids))
    )
    return int(removed_by_age.rowcount or 0) + int(removed_overflow.rowcount or 0)


def requeue_stale_sent_commands(db: Session) -> int:
    timestamp = now_utc()
    commands = db.scalars(
        select(DeviceCommand)
        .where(
            DeviceCommand.status == "sent",
            DeviceCommand.updated_at < timestamp - COMMAND_DELIVERY_LEASE,
            DeviceCommand.expires_at.is_not(None),
            DeviceCommand.expires_at >= timestamp,
        )
        .with_for_update(skip_locked=True)
    ).all()
    requeued = 0
    for command in commands:
        delivery = get_command_metadata(command.command_type)["reliability"]["delivery"]
        if command.retry_count >= int(delivery["max_deliveries"]):
            command.status = "failed"
            command.completed_at = timestamp
            command.last_error = "Command delivery attempts exhausted"
        else:
            command.status = "queued"
            command.last_error = "Delivery lease expired; command queued for retry"
            requeued += 1
        command.updated_at = timestamp
    if commands:
        # Sessions deliberately disable autoflush. The polling query that runs
        # immediately after this function must observe queued retries.
        db.flush()
    return requeued


__all__ = [
    "mask_secrets",
    "public_command_payload",
    "public_command_result",
    "command_history_entry",
    "now_utc",
    "create_device_command",
    "validate_command_request",
    "expire_old_commands",
    "cleanup_device_command_history",
    "requeue_stale_sent_commands",
]
