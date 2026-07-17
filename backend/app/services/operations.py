from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import APP_VERSION
from ..models import Device, DeviceCommand, DeviceTelemetry


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
        interval = int(agent.get("telemetry_interval_seconds") or 60)
        stale_after = max(120, interval * 3)
        if (
            not device.last_seen_at
            or (now - device.last_seen_at).total_seconds() > stale_after
        ):
            items.append(
                {
                    "severity": "critical",
                    "kind": "device_offline",
                    "title": f"Нет связи с {device.name or device.hostname or 'роутером'}",
                    "message": f"Telemetry не поступает более {stale_after} секунд.",
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
    for command in failed:
        items.append(
            {
                "severity": "warning",
                "kind": "command_failed",
                "title": f"Команда {command.command_type} завершилась ошибкой",
                "message": command.last_error or "Агент вернул ошибку выполнения.",
                "device_id": str(command.device_id),
                "command_id": str(command.id),
            }
        )
    return items
