from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from fastapi import APIRouter, Cookie, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import Settings
from ..db import get_db
from ..models import (
    AutomationRule,
    AutomationRun,
    Device,
    EventRecord,
    NotificationRule,
    User,
)
from ..services.auth import settings, web_user_from_session
from ..services.command_registry import COMMAND_REGISTRY
from ..services.events import (
    BLOCKED_AUTOMATION_COMMANDS,
    event_templates,
    public_event,
    validate_automation_action,
    validate_automation_payload,
    validate_automation_trigger,
    validate_notification_channels,
)
from .route_shared import generate_csrf_token, require_web_csrf, templates


router = APIRouter()


def _user_or_redirect(token: str | None, config: Settings, db: Session) -> User | None:
    return web_user_from_session(token, config, db)


@router.get("/events", response_class=HTMLResponse)
def events_page(
    request: Request,
    event_type: str | None = None,
    severity: str | None = None,
    status: str | None = None,
    page: int = 1,
    config: Settings = Depends(settings),
    db: Session = Depends(get_db),
    wrtmonitor_session: str | None = Cookie(default=None),
):
    user = _user_or_redirect(wrtmonitor_session, config, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    query = select(EventRecord)
    if event_type:
        query = query.where(EventRecord.event_type == event_type)
    if severity:
        query = query.where(EventRecord.severity == severity)
    if status:
        query = query.where(EventRecord.status == status)
    page_size = 25
    page = max(1, page)
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    pages = max(1, (total + page_size - 1) // page_size)
    page = min(page, pages)
    event_records = db.scalars(
        query.order_by(EventRecord.last_occurred_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    events = [public_event(item) for item in event_records]
    notification_rules = db.scalars(
        select(NotificationRule).order_by(NotificationRule.name)
    ).all()
    automations = db.scalars(select(AutomationRule).order_by(AutomationRule.name)).all()
    runs = db.scalars(
        select(AutomationRun).order_by(AutomationRun.created_at.desc()).limit(30)
    ).all()
    devices = db.scalars(
        select(Device).where(Device.archived_at.is_(None)).order_by(Device.name)
    ).all()
    commands = [
        {"type": name, **metadata}
        for name, metadata in sorted(COMMAND_REGISTRY.items())
        if name not in BLOCKED_AUTOMATION_COMMANDS
    ]
    response = templates.TemplateResponse(
        request,
        "events.html",
        {
            "user": user,
            "events": events,
            "notification_rules": notification_rules,
            "automations": automations,
            "automation_runs": runs,
            "templates": event_templates(),
            "devices": devices,
            "commands": commands,
            "filters": {
                "event_type": event_type or "",
                "severity": severity or "",
                "status": status or "",
            },
            "pagination": {
                "page": page,
                "pages": pages,
                "total": total,
                "start": (page - 1) * page_size + 1 if total else 0,
                "end": min(page * page_size, total),
            },
            "csrf_token": generate_csrf_token(
                wrtmonitor_session or "", config.jwt_secret
            ),
        },
    )
    response.headers["Cache-Control"] = "no-store"
    return response


def _csrf(token: str | None, csrf_token: str, config: Settings) -> None:
    require_web_csrf(token, csrf_token, config)


@router.post("/events/{event_id}/acknowledge")
def web_acknowledge_event(
    event_id: UUID,
    csrf_token: str = Form(...),
    config: Settings = Depends(settings),
    db: Session = Depends(get_db),
    wrtmonitor_session: str | None = Cookie(default=None),
) -> RedirectResponse:
    _csrf(wrtmonitor_session, csrf_token, config)
    if not _user_or_redirect(wrtmonitor_session, config, db):
        return RedirectResponse("/login", status_code=303)
    item = db.get(EventRecord, event_id)
    if not item:
        raise HTTPException(status_code=404, detail="Событие не найдено")
    if item.status != "resolved":
        item.status = "acknowledged"
        item.acknowledged_at = datetime.now(UTC)
    db.commit()
    return RedirectResponse("/events", status_code=303)


@router.post("/events/{event_id}/snooze")
def web_snooze_event(
    event_id: UUID,
    minutes: int = Form(60),
    csrf_token: str = Form(...),
    config: Settings = Depends(settings),
    db: Session = Depends(get_db),
    wrtmonitor_session: str | None = Cookie(default=None),
) -> RedirectResponse:
    _csrf(wrtmonitor_session, csrf_token, config)
    if not _user_or_redirect(wrtmonitor_session, config, db):
        return RedirectResponse("/login", status_code=303)
    item = db.get(EventRecord, event_id)
    if not item:
        raise HTTPException(status_code=404, detail="Событие не найдено")
    item.snoozed_until = datetime.now(UTC) + timedelta(
        minutes=min(max(minutes, 5), 10080)
    )
    db.commit()
    return RedirectResponse("/events", status_code=303)


@router.post("/events/notification-rules")
def web_create_notification_rule(
    name: str = Form(...),
    device_id: str = Form(""),
    event_types: str = Form(""),
    severities: str = Form("warning,critical"),
    channel_type: str = Form("in_app"),
    target: str = Form(""),
    quiet_enabled: bool = Form(False),
    quiet_start: str = Form("22:00"),
    quiet_end: str = Form("07:00"),
    csrf_token: str = Form(...),
    config: Settings = Depends(settings),
    db: Session = Depends(get_db),
    wrtmonitor_session: str | None = Cookie(default=None),
) -> RedirectResponse:
    _csrf(wrtmonitor_session, csrf_token, config)
    if not _user_or_redirect(wrtmonitor_session, config, db):
        return RedirectResponse("/login", status_code=303)
    if channel_type not in {"in_app", "webhook", "ntfy", "smtp"}:
        raise HTTPException(status_code=422, detail="Канал не поддерживается")
    if channel_type != "in_app" and not target.strip():
        raise HTTPException(status_code=422, detail="Для внешнего канала нужен адрес")
    channel = {"type": channel_type}
    if target.strip():
        channel["to" if channel_type == "smtp" else "url"] = target.strip()
    channels = [channel]
    try:
        channels = validate_notification_channels(channels, config)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    now = datetime.now(UTC)
    db.add(
        NotificationRule(
            id=uuid4(),
            name=name.strip()[:120],
            device_id=UUID(device_id) if device_id else None,
            enabled=True,
            event_types=[v.strip() for v in event_types.split(",") if v.strip()],
            severities=[v.strip() for v in severities.split(",") if v.strip()],
            channels=channels,
            quiet_hours={
                "enabled": quiet_enabled,
                "start": quiet_start,
                "end": quiet_end,
            },
            notify_recovery=True,
            created_at=now,
            updated_at=now,
        )
    )
    db.commit()
    return RedirectResponse("/events", status_code=303)


@router.post("/events/notification-rules/{rule_id}/delete")
def web_delete_notification_rule(
    rule_id: UUID,
    csrf_token: str = Form(...),
    config: Settings = Depends(settings),
    db: Session = Depends(get_db),
    wrtmonitor_session: str | None = Cookie(default=None),
) -> RedirectResponse:
    _csrf(wrtmonitor_session, csrf_token, config)
    if not _user_or_redirect(wrtmonitor_session, config, db):
        return RedirectResponse("/login", status_code=303)
    item = db.get(NotificationRule, rule_id)
    if item:
        db.delete(item)
        db.commit()
    return RedirectResponse("/events", status_code=303)


@router.post("/events/automations")
def web_create_automation(
    name: str = Form(...),
    device_id: str = Form(""),
    trigger_type: str = Form(...),
    action_command: str = Form(...),
    action_payload: str = Form("{}"),
    cooldown_seconds: int = Form(300),
    max_runs_per_hour: int = Form(6),
    dry_run: bool = Form(False),
    allow_disruptive: bool = Form(False),
    csrf_token: str = Form(...),
    config: Settings = Depends(settings),
    db: Session = Depends(get_db),
    wrtmonitor_session: str | None = Cookie(default=None),
) -> RedirectResponse:
    _csrf(wrtmonitor_session, csrf_token, config)
    if not _user_or_redirect(wrtmonitor_session, config, db):
        return RedirectResponse("/login", status_code=303)
    validate_automation_trigger(trigger_type)
    validate_automation_action(action_command, allow_disruptive)
    try:
        payload = json.loads(action_payload or "{}")
        if not isinstance(payload, dict):
            raise ValueError
    except (json.JSONDecodeError, ValueError) as exc:
        raise HTTPException(
            status_code=422, detail="Payload должен быть JSON-объектом"
        ) from exc
    payload = validate_automation_payload(action_command, payload)
    now = datetime.now(UTC)
    db.add(
        AutomationRule(
            id=uuid4(),
            name=name.strip()[:120],
            device_id=UUID(device_id) if device_id else None,
            enabled=True,
            trigger_type=trigger_type.strip(),
            conditions={},
            action_command=action_command,
            action_payload=payload,
            cooldown_seconds=min(max(cooldown_seconds, 5), 86400),
            max_runs_per_hour=min(max(max_runs_per_hour, 1), 60),
            dry_run=dry_run,
            allow_disruptive=allow_disruptive,
            created_at=now,
            updated_at=now,
        )
    )
    db.commit()
    return RedirectResponse("/events", status_code=303)


@router.post("/events/automations/{rule_id}/toggle")
def web_toggle_automation(
    rule_id: UUID,
    csrf_token: str = Form(...),
    config: Settings = Depends(settings),
    db: Session = Depends(get_db),
    wrtmonitor_session: str | None = Cookie(default=None),
) -> RedirectResponse:
    _csrf(wrtmonitor_session, csrf_token, config)
    if not _user_or_redirect(wrtmonitor_session, config, db):
        return RedirectResponse("/login", status_code=303)
    item = db.get(AutomationRule, rule_id)
    if not item:
        raise HTTPException(status_code=404, detail="Правило не найдено")
    item.enabled = not item.enabled
    item.updated_at = datetime.now(UTC)
    db.commit()
    return RedirectResponse("/events", status_code=303)


@router.post("/events/automations/{rule_id}/delete")
def web_delete_automation(
    rule_id: UUID,
    csrf_token: str = Form(...),
    config: Settings = Depends(settings),
    db: Session = Depends(get_db),
    wrtmonitor_session: str | None = Cookie(default=None),
) -> RedirectResponse:
    _csrf(wrtmonitor_session, csrf_token, config)
    if not _user_or_redirect(wrtmonitor_session, config, db):
        return RedirectResponse("/login", status_code=303)
    item = db.get(AutomationRule, rule_id)
    if item:
        db.delete(item)
        db.commit()
    return RedirectResponse("/events", status_code=303)


__all__ = ["router"]
