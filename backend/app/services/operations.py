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
    AutomationRun,
    AuditLog,
    AuthAttempt,
    Device,
    DeviceCommand,
    DeviceTelemetry,
    DeviceTelemetryMetric,
    EventRecord,
    MobilePairingAttempt,
)
from ..models import NetworkClient
from .client_registry import effective_client_presence
from .events import emit_event
from .command_store import cleanup_device_command_history, expire_old_commands
from .command_store import public_command_result
from .telemetry_history import (
    cleanup_device_telemetry,
    cleanup_device_telemetry_metrics,
)
from .terminal_broker import cleanup_terminal_sessions
from .realtime import broker


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
        "realtime": broker.metrics(),
    }


def build_device_diagnostic_report(db: Session, device: Device) -> dict[str, Any]:
    """Build a support report without credentials or raw router configuration."""
    now = datetime.now(UTC)
    telemetry = db.scalars(
        select(DeviceTelemetry)
        .where(DeviceTelemetry.device_id == device.id)
        .order_by(DeviceTelemetry.created_at.desc())
        .limit(1)
    ).first()
    metric = db.scalars(
        select(DeviceTelemetryMetric)
        .where(DeviceTelemetryMetric.device_id == device.id)
        .order_by(DeviceTelemetryMetric.created_at.desc())
        .limit(1)
    ).first()
    diagnostic = db.scalars(
        select(DeviceCommand)
        .where(
            DeviceCommand.device_id == device.id,
            DeviceCommand.command_type == "diagnostics.run",
        )
        .order_by(DeviceCommand.created_at.desc())
        .limit(1)
    ).first()
    payload = telemetry.payload if telemetry else {}
    system = payload.get("system") or {}
    agent = payload.get("agent") or {}
    freshness = _agent_freshness(device, telemetry, now)
    return {
        "schema": "wrtmonitor.support-report.v1",
        "generated_at": now.isoformat(),
        "server_version": APP_VERSION,
        "device": {
            "id": str(device.id),
            "name": device.name,
            "hostname": device.hostname,
            "model": device.model,
            "firmware": device.firmware,
            "status": device.status,
            "last_seen_at": device.last_seen_at.isoformat()
            if device.last_seen_at
            else None,
        },
        "agent": {
            "version": agent.get("version"),
            "status": agent.get("status"),
            "telemetry_interval_seconds": agent.get("telemetry_interval_seconds"),
            "capabilities_reported": len(agent.get("capabilities") or {}),
            "freshness": freshness,
        },
        "system": {
            "uptime_seconds": system.get("uptime"),
            "load_1m": metric.load_1m if metric else None,
            "memory_percent": metric.memory_percent if metric else None,
            "temperature_celsius": metric.temperature_celsius if metric else None,
            "storage_percent": metric.storage_percent if metric else None,
            "client_count": metric.client_count if metric else None,
        },
        "latest_diagnostics": {
            "command_id": str(diagnostic.id),
            "status": diagnostic.status,
            "created_at": diagnostic.created_at.isoformat(),
            "completed_at": diagnostic.completed_at.isoformat()
            if diagnostic.completed_at
            else None,
            "error": diagnostic.last_error,
            "result": public_command_result(diagnostic.command_type, diagnostic.result),
        }
        if diagnostic
        else None,
    }


def operational_notifications(db: Session) -> list[dict[str, Any]]:
    now = datetime.now(UTC)
    events = db.scalars(
        select(EventRecord)
        .where(
            EventRecord.status == "open",
            (EventRecord.snoozed_until.is_(None) | (EventRecord.snoozed_until <= now)),
        )
        .order_by(EventRecord.last_occurred_at.desc())
        .limit(100)
    ).all()
    return [
        {
            "id": str(item.id),
            "severity": item.severity,
            "kind": item.event_type,
            "title": item.title,
            "message": item.message,
            "device_id": str(item.device_id) if item.device_id else None,
            "created_at": item.last_occurred_at.isoformat(),
            "occurrence_count": item.occurrence_count,
        }
        for item in events
    ]


def run_housekeeping(db: Session, config: Settings) -> dict[str, int]:
    now = datetime.now(UTC)
    counters = {
        "offline": 0,
        "online": 0,
        "telemetry": 0,
        "commands": 0,
        "auth": 0,
        "terminal_expired": 0,
        "terminal_deleted": 0,
        "events": 0,
        "clients_offline": 0,
    }
    expire_old_commands(db)
    terminal_cleanup = cleanup_terminal_sessions(db, now=now)
    counters["terminal_expired"] = terminal_cleanup["expired"]
    counters["terminal_deleted"] = terminal_cleanup["deleted"]
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
            emit_event(
                db,
                device_id=device.id,
                event_type=f"device.{desired}",
                severity="critical" if desired == "offline" else "info",
                source="housekeeping",
                title=f"{device.name or device.hostname or 'Роутер'}: {'нет связи' if desired == 'offline' else 'связь восстановлена'}",
                message=f"Состояние изменилось: {previous} → {desired}.",
                fingerprint=f"{device.id}:device.{desired}",
                dedupe_seconds=30,
                config=config,
            )
            counters[desired] += 1
        for client in db.scalars(
            select(NetworkClient).where(
                NetworkClient.device_id == device.id,
                NetworkClient.presence_state != "offline",
            )
        ).all():
            if effective_client_presence(client, now) == "offline":
                client.online = False
                client.presence_state = "offline"
                client.presence_source = "presence_timeout"
                client.updated_at = now
                emit_event(
                    db,
                    device_id=device.id,
                    event_type="client.offline",
                    severity="info",
                    source="housekeeping",
                    title=f"Клиент отключился: {client.display_name or client.hostname or client.mac}",
                    message=f"Последний адрес: {client.ip_address or 'не определён'}.",
                    data={
                        "client_id": str(client.id),
                        "mac": client.mac,
                        "ip": client.ip_address,
                    },
                    fingerprint=f"{device.id}:client.offline:{client.mac}",
                    dedupe_seconds=120,
                    config=config,
                )
                counters["clients_offline"] += 1
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
    event_cutoff = now - timedelta(days=config.event_retention_days)
    removed_events = db.execute(
        delete(EventRecord).where(EventRecord.last_occurred_at < event_cutoff)
    )
    counters["events"] += int(removed_events.rowcount or 0)
    for device in devices:
        overflow = (
            select(EventRecord.id)
            .where(EventRecord.device_id == device.id)
            .order_by(EventRecord.last_occurred_at.desc())
            .offset(config.event_max_per_device)
        )
        result = db.execute(delete(EventRecord).where(EventRecord.id.in_(overflow)))
        counters["events"] += int(result.rowcount or 0)
    db.execute(delete(AutomationRun).where(AutomationRun.created_at < event_cutoff))
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
        devices = db.scalars(
            select(Device).where(Device.archived_at.is_(None)).order_by(Device.name)
        ).all()
        archive.writestr(
            "routers.json",
            json.dumps(
                [build_device_diagnostic_report(db, device) for device in devices],
                ensure_ascii=False,
                indent=2,
            ),
        )
    return data.getvalue()
