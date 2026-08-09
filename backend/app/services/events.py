from __future__ import annotations

from datetime import UTC, datetime, timedelta
import ipaddress
import json
import smtplib
import socket
from email.message import EmailMessage
from typing import Any
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from uuid import UUID, uuid4

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import Settings
from ..models import (
    AutomationRule,
    AutomationRun,
    EventRecord,
    NotificationRule,
)
from .command_registry import COMMAND_REGISTRY
from .command_store import create_device_command, validate_command_request
from .realtime import queue_realtime_event


SEVERITIES = {"info", "warning", "critical"}
EVENT_STATUSES = {"open", "acknowledged", "resolved"}
BLOCKED_AUTOMATION_COMMANDS = {
    "agent.disconnect",
    "agent.ssh_session",
    "agent.bash_script",
    "agent.token_rotate",
    "maintenance.sysupgrade.apply",
    "router.factory_reset",
}


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def public_event(item: EventRecord) -> dict[str, Any]:
    return {
        "id": str(item.id),
        "device_id": str(item.device_id) if item.device_id else None,
        "event_type": item.event_type,
        "severity": item.severity,
        "source": item.source,
        "title": item.title,
        "message": item.message,
        "data": item.event_data,
        "status": item.status,
        "occurrence_count": item.occurrence_count,
        "occurred_at": _iso(item.occurred_at),
        "last_occurred_at": _iso(item.last_occurred_at),
        "acknowledged_at": _iso(item.acknowledged_at),
        "snoozed_until": _iso(item.snoozed_until),
        "resolved_at": _iso(item.resolved_at),
    }


def _quiet_now(rule: NotificationRule, now: datetime) -> bool:
    quiet = rule.quiet_hours or {}
    if not quiet.get("enabled"):
        return False
    try:
        start_hour, start_minute = map(int, str(quiet.get("start", "22:00")).split(":"))
        end_hour, end_minute = map(int, str(quiet.get("end", "07:00")).split(":"))
    except (TypeError, ValueError):
        return False
    minute = now.hour * 60 + now.minute
    start = start_hour * 60 + start_minute
    end = end_hour * 60 + end_minute
    return start <= minute < end if start < end else minute >= start or minute < end


def _rule_matches(rule: NotificationRule, event: EventRecord) -> bool:
    if not rule.enabled or (rule.device_id and rule.device_id != event.device_id):
        return False
    if rule.event_types and event.event_type not in rule.event_types:
        return False
    if rule.severities and event.severity not in rule.severities:
        return False
    if event.event_type.endswith(".recovered") and not rule.notify_recovery:
        return False
    return not _quiet_now(rule, event.occurred_at)


def validate_notification_channels(
    channels: list[dict[str, Any]], config: Settings
) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for raw in channels or [{"type": "in_app"}]:
        channel = dict(raw)
        kind = str(channel.get("type") or "in_app")
        if kind in {"webhook", "ntfy"}:
            channel["url"] = _validated_delivery_url(
                str(channel.get("url") or ""), config
            )
        elif kind == "smtp":
            if not config.smtp_host or not config.smtp_from:
                raise ValueError("SMTP delivery is not configured on the server")
            recipient = str(channel.get("to") or "").strip()
            if not recipient or "@" not in recipient:
                raise ValueError("SMTP recipient is required")
            channel = {"type": "smtp", "to": recipient}
        elif kind != "in_app":
            raise ValueError(f"unsupported notification channel: {kind}")
        channel["type"] = kind
        normalized.append(channel)
    return normalized


def _validated_delivery_url(url: str, config: Settings) -> str:
    parsed = urlparse(url.strip())
    if (
        parsed.scheme not in {"https", "http"}
        or not parsed.hostname
        or parsed.username
        or parsed.password
    ):
        raise ValueError(
            "notification target must be an absolute HTTP(S) URL without credentials"
        )
    if parsed.scheme != "https" and not config.notification_allow_private_targets:
        raise ValueError("notification target must use HTTPS")
    addresses = {
        item[4][0] for item in socket.getaddrinfo(parsed.hostname, parsed.port or 443)
    }
    if not config.notification_allow_private_targets:
        for address in addresses:
            ip = ipaddress.ip_address(address)
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_unspecified:
                raise ValueError("private notification targets are disabled")
    return url.strip()


def _deliver_channel(
    channel: dict[str, Any], event: EventRecord, config: Settings
) -> str:
    kind = str(channel.get("type") or "in_app")
    if kind == "in_app":
        return "delivered"
    payload = json.dumps(public_event(event), ensure_ascii=False).encode()
    if kind in {"webhook", "ntfy"}:
        url = _validated_delivery_url(str(channel.get("url") or ""), config)
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "WrtMonitor/notifications",
        }
        if kind == "ntfy":
            headers.update(
                {
                    "Title": event.title,
                    "Priority": "urgent" if event.severity == "critical" else "default",
                }
            )
            payload = event.message.encode()
        with urlopen(
            Request(url, data=payload, headers=headers, method="POST"), timeout=5
        ) as response:
            if response.status >= 300:
                raise ValueError(f"notification target returned HTTP {response.status}")
        return "delivered"
    if kind == "smtp":
        recipient = str(channel.get("to") or "").strip()
        if not config.smtp_host or not config.smtp_from or not recipient:
            raise ValueError("SMTP delivery is not configured")
        message = EmailMessage()
        message["Subject"] = f"[WrtMonitor] {event.title}"
        message["From"] = config.smtp_from
        message["To"] = recipient
        message.set_content(event.message)
        with smtplib.SMTP(config.smtp_host, config.smtp_port, timeout=5) as smtp:
            if config.smtp_starttls:
                smtp.starttls()
            if config.smtp_username:
                smtp.login(config.smtp_username, config.smtp_password or "")
            smtp.send_message(message)
        return "delivered"
    raise ValueError(f"unsupported notification channel: {kind}")


def deliver_notifications(
    db: Session, event: EventRecord, config: Settings
) -> list[dict[str, str]]:
    results: list[dict[str, str]] = []
    rules = db.scalars(
        select(NotificationRule).where(NotificationRule.enabled.is_(True))
    ).all()
    for rule in rules:
        if not _rule_matches(rule, event):
            continue
        for channel in rule.channels or [{"type": "in_app"}]:
            try:
                result = _deliver_channel(channel, event, config)
                results.append(
                    {
                        "rule_id": str(rule.id),
                        "channel": str(channel.get("type") or "in_app"),
                        "status": result,
                    }
                )
            except (OSError, ValueError, smtplib.SMTPException) as exc:
                results.append(
                    {
                        "rule_id": str(rule.id),
                        "channel": str(channel.get("type") or "unknown"),
                        "status": "failed",
                        "error": str(exc)[:300],
                    }
                )
    return results


def _condition_matches(conditions: dict[str, Any], event: EventRecord) -> bool:
    severity = conditions.get("severity")
    if severity and event.severity != severity:
        return False
    field = str(conditions.get("data_field") or "")
    if field and event.event_data.get(field) != conditions.get("equals"):
        return False
    return True


def validate_automation_action(
    command_type: str, allow_disruptive: bool
) -> dict[str, Any]:
    metadata = COMMAND_REGISTRY.get(command_type)
    if not metadata or command_type in BLOCKED_AUTOMATION_COMMANDS:
        raise HTTPException(
            status_code=422, detail="Command is not allowed in automation"
        )
    risk = str(metadata.get("risk_level") or "")
    if (
        risk.startswith("level_4") or risk.startswith("level_5")
    ) and not allow_disruptive:
        raise HTTPException(
            status_code=422, detail="Disruptive automation requires explicit permission"
        )
    return metadata


def validate_automation_trigger(trigger_type: str) -> str:
    value = trigger_type.strip()
    if not value or value.startswith("command."):
        raise HTTPException(
            status_code=422,
            detail="Command lifecycle events cannot trigger another command",
        )
    return value


def validate_automation_payload(
    command_type: str, payload: dict[str, Any]
) -> dict[str, Any]:
    return validate_command_request(
        command_type=command_type,
        payload=payload,
        confirmed=True,
    )


def run_automations(
    db: Session, event: EventRecord, now: datetime | None = None
) -> list[AutomationRun]:
    now = now or datetime.now(UTC)
    if int(event.event_data.get("automation_depth") or 0) >= 3:
        return []
    rules = db.scalars(
        select(AutomationRule).where(
            AutomationRule.enabled.is_(True),
            AutomationRule.trigger_type == event.event_type,
        )
    ).all()
    runs: list[AutomationRun] = []
    for rule in rules:
        if rule.device_id and rule.device_id != event.device_id:
            continue
        if not event.device_id or not _condition_matches(rule.conditions or {}, event):
            continue
        reason = ""
        if rule.last_triggered_at and rule.last_triggered_at > now - timedelta(
            seconds=rule.cooldown_seconds
        ):
            reason = "cooldown"
        hourly = (
            db.scalar(
                select(func.count(AutomationRun.id)).where(
                    AutomationRun.rule_id == rule.id,
                    AutomationRun.created_at >= now - timedelta(hours=1),
                    AutomationRun.status.in_(("dry_run", "queued")),
                )
            )
            or 0
        )
        if hourly >= rule.max_runs_per_hour:
            reason = "rate_limited"
        try:
            validate_automation_action(rule.action_command, rule.allow_disruptive)
        except HTTPException as exc:
            reason = str(exc.detail)
        run = AutomationRun(
            id=uuid4(),
            rule_id=rule.id,
            event_id=event.id,
            command_id=None,
            status="skipped" if reason else ("dry_run" if rule.dry_run else "queued"),
            message=reason
            or (
                "Dry run: command was not queued" if rule.dry_run else "Command queued"
            ),
            created_at=now,
        )
        if not reason and not rule.dry_run:
            payload = dict(rule.action_payload or {})
            try:
                normalized = validate_command_request(
                    command_type=rule.action_command,
                    payload=payload,
                    confirmed=True,
                )
                command = create_device_command(
                    db,
                    device_id=event.device_id,
                    command_type=rule.action_command,
                    payload=normalized,
                    created_by=None,
                    source="automation",
                    idempotency_key=f"automation:{rule.id}:{event.id}",
                )
                run.command_id = command.id
            except HTTPException as exc:
                run.status = "failed"
                run.message = str(exc.detail)
        if not reason:
            rule.last_triggered_at = now
            rule.updated_at = now
        db.add(run)
        runs.append(run)
    return runs


def emit_event(
    db: Session,
    *,
    event_type: str,
    title: str,
    message: str = "",
    device_id: UUID | None = None,
    severity: str = "info",
    source: str = "server",
    data: dict[str, Any] | None = None,
    fingerprint: str | None = None,
    dedupe_seconds: int = 60,
    config: Settings | None = None,
) -> tuple[EventRecord, bool]:
    if severity not in SEVERITIES:
        raise ValueError("invalid event severity")
    now = datetime.now(UTC)
    key = fingerprint or f"{device_id or 'server'}:{event_type}"
    existing = db.scalars(
        select(EventRecord)
        .where(
            EventRecord.fingerprint == key,
            EventRecord.status != "resolved",
            EventRecord.last_occurred_at
            >= now - timedelta(seconds=max(0, dedupe_seconds)),
        )
        .order_by(EventRecord.last_occurred_at.desc())
        .limit(1)
    ).first()
    if existing:
        existing.last_occurred_at = now
        existing.occurrence_count += 1
        existing.message = message
        existing.event_data = {**(existing.event_data or {}), **(data or {})}
        if existing.status == "acknowledged":
            existing.status = "open"
            existing.acknowledged_at = None
        existing.snoozed_until = None
        return existing, False
    item = EventRecord(
        id=uuid4(),
        device_id=device_id,
        event_type=event_type,
        severity=severity,
        source=source,
        title=title[:200],
        message=message,
        event_data=data or {},
        fingerprint=key[:255],
        status="open",
        occurrence_count=1,
        occurred_at=now,
        last_occurred_at=now,
    )
    db.add(item)
    db.flush()
    if device_id:
        queue_realtime_event(db, device_id, "event.created", public_event(item))
    run_automations(db, item, now)
    if config:
        results = deliver_notifications(db, item, config)
        if results:
            item.event_data = {**item.event_data, "delivery": results}
    return item, True


def resolve_events(
    db: Session,
    *,
    device_id: UUID,
    event_type: str,
    title: str,
    message: str,
    config: Settings | None = None,
) -> EventRecord | None:
    active = db.scalars(
        select(EventRecord).where(
            EventRecord.device_id == device_id,
            EventRecord.event_type == event_type,
            EventRecord.status != "resolved",
        )
    ).all()
    if not active:
        return None
    now = datetime.now(UTC)
    for item in active:
        item.status = "resolved"
        item.resolved_at = now
    recovery, _ = emit_event(
        db,
        device_id=device_id,
        event_type=f"{event_type}.recovered",
        severity="info",
        title=title,
        message=message,
        source="server",
        data={"recovered_event_ids": [str(item.id) for item in active]},
        dedupe_seconds=10,
        config=config,
    )
    return recovery


def event_templates() -> list[dict[str, Any]]:
    return [
        {
            "id": "wan-recovery-diagnostics",
            "name": "Диагностика после сбоя WAN",
            "trigger_type": "wan.changed",
            "action_command": "diagnostics.run",
            "action_payload": {"checks": ["server", "dns", "route"]},
            "cooldown_seconds": 300,
        },
        {
            "id": "high-load-diagnostics",
            "name": "Диагностика при высокой нагрузке",
            "trigger_type": "telemetry.load.high",
            "action_command": "diagnostics.run",
            "action_payload": {"checks": ["dependencies", "route"]},
            "cooldown_seconds": 900,
        },
        {
            "id": "client-online-refresh",
            "name": "Обновить список интерфейсов при появлении клиента",
            "trigger_type": "client.online",
            "action_command": "network.interfaces",
            "action_payload": {},
            "cooldown_seconds": 120,
        },
    ]


__all__ = [
    "emit_event",
    "resolve_events",
    "public_event",
    "deliver_notifications",
    "run_automations",
    "validate_automation_action",
    "validate_automation_trigger",
    "validate_automation_payload",
    "validate_notification_channels",
    "event_templates",
]
