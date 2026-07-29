from datetime import UTC, datetime, timedelta
import io
import json
from typing import Any
import zipfile

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from ..config import APP_VERSION
from ..config import Settings
from ..models import (
    AuditLog,
    AuthAttempt,
    Device,
    DeviceCommand,
    DeviceTelemetry,
    MobilePairingAttempt,
)
from .command_store import cleanup_device_command_history, expire_old_commands
from .telemetry_history import (
    cleanup_device_telemetry,
    cleanup_device_telemetry_metrics,
)


TERMINAL_COMMAND_STATES = ("done", "success", "failed", "expired", "cancelled")


def _agent_freshness(
    device: Device, telemetry: DeviceTelemetry | None, now: datetime
) -> dict[str, Any]:
    agent = (telemetry.payload.get("agent") or {}) if telemetry else {}
    interval = max(5, int(agent.get("telemetry_interval_seconds") or 60))
    stale_after = max(30, interval * 3)
    age = (
        int((now - device.last_seen_at).total_seconds())
        if device.last_seen_at
        else None
    )
    return {
        "interval_seconds": interval,
        "stale_after_seconds": stale_after,
        "age_seconds": age,
        "fresh": age is not None and age <= stale_after,
    }


def operation_metrics(db: Session) -> dict[str, Any]:
    now = datetime.now(UTC)
    status_rows = db.execute(
        select(DeviceCommand.status, func.count(DeviceCommand.id)).group_by(
            DeviceCommand.status
        )
    ).all()
    queued_at = db.scalar(
        select(func.min(DeviceCommand.created_at)).where(
            DeviceCommand.status == "queued"
        )
    )
    freshness: list[dict[str, Any]] = []
    for device in db.scalars(select(Device).where(Device.archived_at.is_(None))).all():
        telemetry = db.scalars(
            select(DeviceTelemetry)
            .where(DeviceTelemetry.device_id == device.id)
            .order_by(DeviceTelemetry.created_at.desc())
            .limit(1)
        ).first()
        state = _agent_freshness(device, telemetry, now)
        state.update(
            {"device_id": str(device.id), "name": device.name or device.hostname}
        )
        freshness.append(state)
    return {
        "generated_at": now.isoformat(),
        "command_queue": {
            "by_status": {str(status): int(count) for status, count in status_rows},
            "active": sum(
                int(count)
                for status, count in status_rows
                if status not in TERMINAL_COMMAND_STATES
            ),
            "oldest_queued_age_seconds": int((now - queued_at).total_seconds())
            if queued_at
            else None,
        },
        "agents": {
            "total": len(freshness),
            "fresh": sum(1 for item in freshness if item["fresh"]),
            "stale": sum(1 for item in freshness if not item["fresh"]),
            "items": freshness,
        },
    }


def operational_notifications(db: Session) -> list[dict[str, Any]]:
    now = datetime.now(UTC)
    items: list[dict[str, Any]] = []
    devices = db.scalars(
        select(Device).where(Device.archived_at.is_(None)).order_by(Device.created_at)
    ).all()
    for device in devices:
        telemetry = db.scalars(
            select(DeviceTelemetry)
            .where(DeviceTelemetry.device_id == device.id)
            .order_by(DeviceTelemetry.created_at.desc())
            .limit(1)
        ).first()
        agent = (telemetry.payload.get("agent") or {}) if telemetry else {}
        freshness = _agent_freshness(device, telemetry, now)
        if not freshness["fresh"]:
            items.append(
                {
                    "severity": "critical",
                    "kind": "device_offline",
                    "title": f"Нет связи с {device.name or device.hostname or 'роутером'}",
                    "message": f"Telemetry не поступает более {freshness['stale_after_seconds']} секунд.",
                    "device_id": str(device.id),
                }
            )
        agent_version = str(agent.get("version") or "")
        if agent_version and agent_version != APP_VERSION:
            items.append(
                {
                    "severity": "warning",
                    "kind": "agent_update",
                    "title": f"Доступно обновление агента {APP_VERSION}",
                    "message": f"На {device.name or device.hostname or 'роутере'} установлена версия {agent_version}.",
                    "device_id": str(device.id),
                }
            )
    failed = db.scalars(
        select(DeviceCommand)
        .where(
            DeviceCommand.status == "failed",
            DeviceCommand.updated_at >= now - timedelta(hours=24),
        )
        .order_by(DeviceCommand.updated_at.desc())
        .limit(20)
    ).all()
    kind_by_command = {
        "agent.update": ("agent_update_failed", "Ошибка обновления агента"),
        "maintenance.backup.create": ("backup_failed", "Ошибка резервного копирования"),
        "maintenance.backup.restore": (
            "backup_failed",
            "Ошибка восстановления резервной копии",
        ),
        "network.set_multiwan": (
            "wan_failover_failed",
            "Ошибка настройки WAN failover",
        ),
    }
    for command in failed:
        kind, title = kind_by_command.get(
            command.command_type,
            ("command_failed", f"Команда {command.command_type} завершилась ошибкой"),
        )
        items.append(
            {
                "severity": "warning",
                "kind": kind,
                "title": title,
                "message": command.last_error or "Агент вернул ошибку выполнения.",
                "device_id": str(command.device_id),
                "command_id": str(command.id),
            }
        )
    recent_events = db.scalars(
        select(AuditLog)
        .where(
            AuditLog.action.in_(("device.online", "device.offline", "wan.failover")),
            AuditLog.created_at >= now - timedelta(hours=24),
        )
        .order_by(AuditLog.created_at.desc())
        .limit(50)
    ).all()
    for event in recent_events:
        details = event.details or {}
        items.append(
            {
                "severity": "info" if event.action == "device.online" else "warning",
                "kind": event.action,
                "title": details.get("title") or event.action,
                "message": details.get("message")
                or "Состояние подключения изменилось.",
                "device_id": event.object_id,
                "created_at": event.created_at.isoformat(),
            }
        )
    return items


def run_housekeeping(db: Session, config: Settings) -> dict[str, int]:
    now = datetime.now(UTC)
    counters = {"offline": 0, "online": 0, "telemetry": 0, "commands": 0, "auth": 0}
    expire_old_commands(db)
    devices = db.scalars(select(Device).where(Device.archived_at.is_(None))).all()
    for device in devices:
        telemetry = db.scalars(
            select(DeviceTelemetry)
            .where(DeviceTelemetry.device_id == device.id)
            .order_by(DeviceTelemetry.created_at.desc())
            .limit(1)
        ).first()
        fresh = _agent_freshness(device, telemetry, now)["fresh"]
        desired = "online" if fresh else "offline"
        if device.status != desired:
            previous = device.status
            device.status = desired
            device.updated_at = now
            db.add(
                AuditLog(
                    id=__import__("uuid").uuid4(),
                    user_id=None,
                    action=f"device.{desired}",
                    object_type="device",
                    object_id=str(device.id),
                    details={
                        "title": f"{device.name or device.hostname or 'Роутер'}: {desired}",
                        "message": f"Состояние изменилось: {previous} → {desired}.",
                    },
                    created_at=now,
                )
            )
            counters[desired] += 1
        counters["telemetry"] += (
            cleanup_device_telemetry(
                db, device.id, config.telemetry_retention_per_device
            )
            or 0
        )
        counters["telemetry"] += (
            cleanup_device_telemetry_metrics(
                db, device.id, config.telemetry_metric_retention_days
            )
            or 0
        )
        counters["commands"] += cleanup_device_command_history(
            db,
            device.id,
            config.command_history_retention_days,
            config.command_history_max_per_device,
        )
    auth_cutoff = now - timedelta(days=7)
    for model in (AuthAttempt, MobilePairingAttempt):
        result = db.execute(delete(model).where(model.created_at < auth_cutoff))
        counters["auth"] += int(result.rowcount or 0)
    db.commit()
    return counters


def build_server_diagnostic_archive(db: Session, config: Settings) -> bytes:
    data = io.BytesIO()
    with zipfile.ZipFile(data, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            "server.json",
            json.dumps(
                {
                    "version": APP_VERSION,
                    "public_server_url": config.public_server_url,
                    "telemetry_retention_per_device": config.telemetry_retention_per_device,
                    "telemetry_metric_retention_days": config.telemetry_metric_retention_days,
                    "command_history_retention_days": config.command_history_retention_days,
                    "command_history_max_per_device": config.command_history_max_per_device,
                },
                ensure_ascii=False,
                indent=2,
            ),
        )
        archive.writestr(
            "operations.json",
            json.dumps(operation_metrics(db), ensure_ascii=False, indent=2),
        )
        archive.writestr(
            "notifications.json",
            json.dumps(operational_notifications(db), ensure_ascii=False, indent=2),
        )
    return data.getvalue()
