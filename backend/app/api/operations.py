from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import (
    AutomationRule,
    AutomationRun,
    Device,
    EventRecord,
    FeedbackRecord,
    NotificationRule,
    User,
)
from ..services.auth import current_user
from ..config import APP_VERSION, load_settings
from ..services.operations import (
    build_device_diagnostic_report,
    build_server_diagnostic_archive,
    operation_metrics,
    operational_notifications,
    store_feedback,
)
from ..services.events import (
    event_templates,
    public_event,
    validate_automation_action,
    validate_automation_payload,
    validate_automation_trigger,
    validate_notification_channels,
)


router = APIRouter(prefix="/api/v1/operations")


class NotificationRulePayload(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    device_id: UUID | None = None
    enabled: bool = True
    event_types: list[str] = Field(default_factory=list)
    severities: list[str] = Field(default_factory=list)
    channels: list[dict[str, Any]] = Field(default_factory=lambda: [{"type": "in_app"}])
    quiet_hours: dict[str, Any] = Field(default_factory=dict)
    notify_recovery: bool = True


class AutomationRulePayload(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    device_id: UUID | None = None
    enabled: bool = True
    trigger_type: str = Field(min_length=1, max_length=120)
    conditions: dict[str, Any] = Field(default_factory=dict)
    action_command: str = Field(min_length=1, max_length=80)
    action_payload: dict[str, Any] = Field(default_factory=dict)
    cooldown_seconds: int = Field(default=300, ge=5, le=86400)
    max_runs_per_hour: int = Field(default=6, ge=1, le=60)
    dry_run: bool = False
    allow_disruptive: bool = False


class FeedbackPayload(BaseModel):
    category: str = Field(pattern="^(bug|idea|usability|other)$")
    message: str = Field(min_length=10, max_length=4000)
    device_id: UUID | None = None
    source: str = Field(default="api", pattern="^(web|android|api)$")
    app_version: str | None = Field(default=None, max_length=40)
    client_context: dict[str, str] = Field(default_factory=dict)


def _notification_rule(item: NotificationRule) -> dict[str, Any]:
    return {
        "id": str(item.id),
        "device_id": str(item.device_id) if item.device_id else None,
        "name": item.name,
        "enabled": item.enabled,
        "event_types": item.event_types,
        "severities": item.severities,
        "channels": item.channels,
        "quiet_hours": item.quiet_hours,
        "notify_recovery": item.notify_recovery,
        "updated_at": item.updated_at.isoformat(),
    }


def _automation_rule(item: AutomationRule) -> dict[str, Any]:
    return {
        "id": str(item.id),
        "device_id": str(item.device_id) if item.device_id else None,
        "name": item.name,
        "enabled": item.enabled,
        "trigger_type": item.trigger_type,
        "conditions": item.conditions,
        "action_command": item.action_command,
        "action_payload": item.action_payload,
        "cooldown_seconds": item.cooldown_seconds,
        "max_runs_per_hour": item.max_runs_per_hour,
        "dry_run": item.dry_run,
        "allow_disruptive": item.allow_disruptive,
        "last_triggered_at": item.last_triggered_at.isoformat()
        if item.last_triggered_at
        else None,
        "updated_at": item.updated_at.isoformat(),
    }


@router.get("/notifications")
def notifications(
    _: User = Depends(current_user), db: Session = Depends(get_db)
) -> list[dict]:
    return operational_notifications(db)


@router.get("/events")
def events(
    device_id: UUID | None = None,
    event_type: str | None = None,
    severity: str | None = None,
    status: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    _: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    query = select(EventRecord)
    if device_id:
        query = query.where(EventRecord.device_id == device_id)
    if event_type:
        query = query.where(EventRecord.event_type == event_type)
    if severity:
        query = query.where(EventRecord.severity == severity)
    if status:
        query = query.where(EventRecord.status == status)
    items = db.scalars(
        query.order_by(EventRecord.last_occurred_at.desc()).offset(offset).limit(limit)
    ).all()
    return [public_event(item) for item in items]


@router.post("/events/{event_id}/acknowledge")
def acknowledge_event(
    event_id: UUID,
    _: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    item = db.get(EventRecord, event_id)
    if not item:
        raise HTTPException(status_code=404, detail="Event not found")
    if item.status != "resolved":
        item.status = "acknowledged"
        item.acknowledged_at = datetime.now(UTC)
    db.commit()
    return public_event(item)


@router.post("/events/{event_id}/snooze")
def snooze_event(
    event_id: UUID,
    minutes: int = Query(default=60, ge=5, le=10080),
    _: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    item = db.get(EventRecord, event_id)
    if not item:
        raise HTTPException(status_code=404, detail="Event not found")
    item.snoozed_until = datetime.now(UTC) + timedelta(minutes=minutes)
    db.commit()
    return public_event(item)


@router.get("/notification-rules")
def notification_rules(
    _: User = Depends(current_user), db: Session = Depends(get_db)
) -> list[dict[str, Any]]:
    return [
        _notification_rule(item)
        for item in db.scalars(
            select(NotificationRule).order_by(NotificationRule.name)
        ).all()
    ]


@router.post("/notification-rules")
def create_notification_rule(
    payload: NotificationRulePayload,
    _: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    try:
        channels = validate_notification_channels(payload.channels, load_settings())
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    now = datetime.now(UTC)
    values = payload.model_dump()
    values["channels"] = channels
    item = NotificationRule(id=uuid4(), created_at=now, updated_at=now, **values)
    db.add(item)
    db.commit()
    return _notification_rule(item)


@router.put("/notification-rules/{rule_id}")
def update_notification_rule(
    rule_id: UUID,
    payload: NotificationRulePayload,
    _: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    item = db.get(NotificationRule, rule_id)
    if not item:
        raise HTTPException(status_code=404, detail="Notification rule not found")
    try:
        channels = validate_notification_channels(payload.channels, load_settings())
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    values = payload.model_dump()
    values["channels"] = channels
    for key, value in values.items():
        setattr(item, key, value)
    item.updated_at = datetime.now(UTC)
    db.commit()
    return _notification_rule(item)


@router.delete("/notification-rules/{rule_id}", status_code=204)
def delete_notification_rule(
    rule_id: UUID, _: User = Depends(current_user), db: Session = Depends(get_db)
) -> None:
    db.execute(delete(NotificationRule).where(NotificationRule.id == rule_id))
    db.commit()


@router.get("/automation/templates")
def automation_templates(_: User = Depends(current_user)) -> list[dict[str, Any]]:
    return event_templates()


@router.get("/automation-rules")
def automation_rules(
    _: User = Depends(current_user), db: Session = Depends(get_db)
) -> list[dict[str, Any]]:
    return [
        _automation_rule(item)
        for item in db.scalars(
            select(AutomationRule).order_by(AutomationRule.name)
        ).all()
    ]


@router.post("/automation-rules")
def create_automation_rule(
    payload: AutomationRulePayload,
    _: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    validate_automation_action(payload.action_command, payload.allow_disruptive)
    validate_automation_trigger(payload.trigger_type)
    normalized_action = validate_automation_payload(
        payload.action_command, payload.action_payload
    )
    now = datetime.now(UTC)
    values = payload.model_dump()
    values["action_payload"] = normalized_action
    item = AutomationRule(id=uuid4(), created_at=now, updated_at=now, **values)
    db.add(item)
    db.commit()
    return _automation_rule(item)


@router.put("/automation-rules/{rule_id}")
def update_automation_rule(
    rule_id: UUID,
    payload: AutomationRulePayload,
    _: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    validate_automation_action(payload.action_command, payload.allow_disruptive)
    validate_automation_trigger(payload.trigger_type)
    normalized_action = validate_automation_payload(
        payload.action_command, payload.action_payload
    )
    item = db.get(AutomationRule, rule_id)
    if not item:
        raise HTTPException(status_code=404, detail="Automation rule not found")
    values = payload.model_dump()
    values["action_payload"] = normalized_action
    for key, value in values.items():
        setattr(item, key, value)
    item.updated_at = datetime.now(UTC)
    db.commit()
    return _automation_rule(item)


@router.delete("/automation-rules/{rule_id}", status_code=204)
def delete_automation_rule(
    rule_id: UUID, _: User = Depends(current_user), db: Session = Depends(get_db)
) -> None:
    db.execute(delete(AutomationRule).where(AutomationRule.id == rule_id))
    db.commit()


@router.get("/automation-runs")
def automation_runs(
    limit: int = Query(default=50, ge=1, le=200),
    _: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    items = db.scalars(
        select(AutomationRun).order_by(AutomationRun.created_at.desc()).limit(limit)
    ).all()
    return [
        {
            "id": str(item.id),
            "rule_id": str(item.rule_id),
            "event_id": str(item.event_id) if item.event_id else None,
            "command_id": str(item.command_id) if item.command_id else None,
            "status": item.status,
            "message": item.message,
            "created_at": item.created_at.isoformat(),
        }
        for item in items
    ]


@router.get("/metrics")
def metrics(_: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    return operation_metrics(db)


@router.post("/feedback", status_code=201)
def create_feedback(
    payload: FeedbackPayload,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    if payload.device_id and not db.get(Device, payload.device_id):
        raise HTTPException(status_code=404, detail="Device not found")
    allowed_context = {"platform", "os_version", "locale", "screen"}
    context = {
        key: str(value)[:160]
        for key, value in payload.client_context.items()
        if key in allowed_context
    }
    try:
        item, duplicate = store_feedback(
            db,
            user_id=user.id,
            device_id=payload.device_id,
            source=payload.source,
            category=payload.category,
            message=payload.message,
            app_version=payload.app_version,
            client_context=context,
        )
    except ValueError as exc:
        if str(exc) == "feedback_rate_limited":
            raise HTTPException(
                status_code=429,
                detail={
                    "code": "feedback_rate_limited",
                    "message": "Too many feedback messages. Try again later.",
                },
            ) from exc
        raise
    db.commit()
    return {
        "id": str(item.id),
        "status": item.status,
        "created_at": item.created_at.isoformat(),
        "duplicate": duplicate,
    }


@router.get("/feedback")
def list_feedback(
    limit: int = Query(default=20, ge=1, le=100),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    items = db.scalars(
        select(FeedbackRecord)
        .where(FeedbackRecord.user_id == user.id)
        .order_by(FeedbackRecord.created_at.desc())
        .limit(limit)
    ).all()
    return [
        {
            "id": str(item.id),
            "device_id": str(item.device_id) if item.device_id else None,
            "source": item.source,
            "category": item.category,
            "message": item.message,
            "app_version": item.app_version,
            "status": item.status,
            "created_at": item.created_at.isoformat(),
        }
        for item in items
    ]


@router.get("/diagnostics/report/{device_id}")
def diagnostic_report(
    device_id: UUID,
    _: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> JSONResponse:
    device = db.get(Device, device_id)
    if not device or device.archived_at:
        raise HTTPException(status_code=404, detail="Device not found")
    return JSONResponse(
        build_device_diagnostic_report(db, device),
        headers={
            "Content-Disposition": f'attachment; filename="wrtmonitor-{device_id}-report.json"'
        },
    )


@router.get("/diagnostics/archive")
def diagnostic_archive(
    _: User = Depends(current_user), db: Session = Depends(get_db)
) -> StreamingResponse:
    config = load_settings()
    import io

    data = io.BytesIO(build_server_diagnostic_archive(db, config))
    return StreamingResponse(
        data,
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="wrtmonitor-server-{APP_VERSION}-diagnostics.zip"'
        },
    )
