from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import DeviceTelemetry, NetworkClient, User
from ..schemas import TelemetryRequest
from ..services.auth import current_user, device_from_token, settings
from ..services.agent_updates import queue_automatic_agent_update
from ..services.client_registry import (
    client_inventory_summary,
    effective_client_presence,
    sync_client_inventory,
)
from ..services.devices import get_latest_agent_status, get_user_device_or_404
from ..services.telemetry import (
    TELEMETRY_STALE_SECONDS,
    build_telemetry_summary,
    cleanup_device_telemetry,
    cleanup_device_telemetry_metrics,
    device_telemetry_history,
    normalize_clients_summary,
    normalize_network_summary,
    normalize_services_summary,
    normalize_system_summary,
    normalize_wifi_summary,
    record_device_telemetry_metric,
    telemetry_alerts,
)
from ..services.telemetry_security import sanitize_telemetry_payload
from ..services.data_state import subsystem_data_state, telemetry_data_state
from ..services.wan_events import record_wan_transition
from ..services.realtime import queue_realtime_event
from ..services.events import emit_event, resolve_events


router = APIRouter()


@router.get("/api/v1/devices/{device_id}/telemetry/history")
def telemetry_history(
    device_id: UUID,
    limit: int = Query(default=60, ge=2, le=120),
    range_name: str | None = Query(
        default=None, alias="range", pattern="^(live|24h|7d|30d)$"
    ),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    get_user_device_or_404(db, user, device_id)
    return {
        "device_id": str(device_id),
        "range": range_name or "recent",
        "points": device_telemetry_history(db, device_id, limit, range_name),
    }


@router.get("/api/v1/devices/{device_id}/telemetry/latest")
def latest_device_telemetry(
    device_id: UUID, user: User = Depends(current_user), db: Session = Depends(get_db)
) -> dict[str, Any]:
    get_user_device_or_404(db, user, device_id)
    telemetry = db.scalars(
        select(DeviceTelemetry)
        .where(DeviceTelemetry.device_id == device_id)
        .order_by(DeviceTelemetry.created_at.desc())
        .limit(1)
    ).first()
    if not telemetry:
        state = telemetry_data_state(
            None,
            observed_at=None,
            age_seconds=None,
            stale_after_seconds=TELEMETRY_STALE_SECONDS,
        )
        return {
            "device_id": str(device_id),
            "telemetry": None,
            "created_at": None,
            "age_seconds": None,
            "is_stale": True,
            "source": None,
            "data_state": state,
            "summary": None,
            "agent": None,
            "wifi": None,
            "network": None,
            "clients": None,
            "system": None,
            "services": None,
            "alerts": telemetry_alerts(None, None),
        }
    age_seconds = max(
        0, int((datetime.now(UTC) - telemetry.created_at).total_seconds())
    )
    clients = client_inventory_summary(db, device_id)
    observed_clients = normalize_clients_summary(telemetry.payload)
    clients["traffic_available"] = observed_clients.get("traffic_available")
    clients["traffic_status"] = observed_clients.get("traffic_status")
    clients["traffic_diagnostics"] = observed_clients.get("traffic_diagnostics")
    state = telemetry_data_state(
        telemetry.payload,
        observed_at=telemetry.created_at,
        age_seconds=age_seconds,
        stale_after_seconds=TELEMETRY_STALE_SECONDS,
    )
    wifi = normalize_wifi_summary(telemetry.payload)
    network = normalize_network_summary(telemetry.payload)
    system = normalize_system_summary(telemetry.payload)
    services = normalize_services_summary(telemetry.payload)
    wifi["data_state"] = subsystem_data_state(
        telemetry.payload.get("wifi"),
        parent_state=state,
        available=wifi.get("available"),
        configured=bool(wifi.get("radios")),
    )
    network["data_state"] = subsystem_data_state(
        telemetry.payload.get("network"),
        parent_state=state,
        configured=bool(network.get("interfaces")),
    )
    clients["data_state"] = subsystem_data_state(
        telemetry.payload.get("clients"), parent_state=state
    )
    system["data_state"] = subsystem_data_state(
        telemetry.payload.get("system"), parent_state=state
    )
    return {
        "device_id": str(device_id),
        "telemetry": telemetry.payload,
        "created_at": telemetry.created_at.isoformat(),
        "age_seconds": age_seconds,
        "is_stale": age_seconds > TELEMETRY_STALE_SECONDS,
        "source": "agent",
        "data_state": state,
        "summary": build_telemetry_summary(telemetry.payload),
        "agent": get_latest_agent_status(db, device_id),
        "wifi": wifi,
        "network": network,
        "clients": clients,
        "system": system,
        "services": services,
        "alerts": telemetry_alerts(telemetry.payload, age_seconds),
    }


@router.post("/api/v1/agent/telemetry")
def agent_telemetry(
    payload: TelemetryRequest,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    device = device_from_token(authorization, db)
    if device.archived_at is not None:
        raise HTTPException(status_code=403, detail="Device is archived")
    if device.id != payload.device_id:
        raise HTTPException(status_code=403, detail="Device token mismatch")
    clean_telemetry = sanitize_telemetry_payload(payload.telemetry)
    now = datetime.now(UTC)
    prior_device_status = device.status
    prior_clients = {
        item.id: effective_client_presence(item, now)
        for item in db.scalars(
            select(NetworkClient).where(NetworkClient.device_id == device.id)
        ).all()
    }
    previous = db.scalars(
        select(DeviceTelemetry)
        .where(DeviceTelemetry.device_id == device.id)
        .order_by(DeviceTelemetry.created_at.desc())
        .limit(1)
    ).first()
    device.status, device.last_seen_at, device.updated_at = "online", now, now
    db.add(
        DeviceTelemetry(
            id=uuid4(), device_id=device.id, payload=clean_telemetry, created_at=now
        )
    )
    db.flush()
    record_device_telemetry_metric(db, device.id, clean_telemetry, now)
    sync_client_inventory(db, device.id, clean_telemetry, now)
    record_wan_transition(
        db,
        device.id,
        previous.payload if previous else None,
        clean_telemetry,
    )
    queue_automatic_agent_update(
        db, device_id=device.id, telemetry=clean_telemetry, now=now
    )
    cleanup_device_telemetry(db, device.id, settings().telemetry_retention_per_device)
    cleanup_device_telemetry_metrics(
        db, device.id, settings().telemetry_metric_retention_days
    )
    queue_realtime_event(
        db,
        device.id,
        "telemetry.updated",
        {"created_at": now.isoformat(), "status": "online"},
    )
    config = settings()
    router_name = device.name or device.hostname or "Роутер"
    if prior_device_status != "online":
        resolve_events(
            db,
            device_id=device.id,
            event_type="device.offline",
            title=f"{router_name} снова в сети",
            message="Связь с агентом восстановлена.",
            config=config,
        )
        emit_event(
            db,
            device_id=device.id,
            event_type="device.online",
            severity="info",
            title=f"{router_name} в сети",
            message="Агент возобновил отправку telemetry.",
            fingerprint=f"{device.id}:device.online:{now.date()}",
            dedupe_seconds=30,
            config=config,
        )
    current_clients = db.scalars(
        select(NetworkClient).where(NetworkClient.device_id == device.id)
    ).all()
    for client in current_clients:
        current_presence = effective_client_presence(client, now)
        previous_presence = prior_clients.get(client.id, "offline")
        if current_presence == "online" and previous_presence != "online":
            emit_event(
                db,
                device_id=device.id,
                event_type="client.online",
                severity="info",
                title=f"Клиент в сети: {client.display_name or client.hostname or client.mac}",
                message=f"{client.ip_address or 'Адрес не назначен'} · {client.interface or 'интерфейс не определён'}",
                source="telemetry",
                data={
                    "client_id": str(client.id),
                    "mac": client.mac,
                    "ip": client.ip_address,
                },
                fingerprint=f"{device.id}:client.online:{client.mac}",
                dedupe_seconds=120,
                config=config,
            )
    alerts = telemetry_alerts(clean_telemetry, 0)
    active_codes = {str(item.get("code")) for item in alerts}
    for alert in alerts:
        code = str(alert.get("code") or "unknown")
        emit_event(
            db,
            device_id=device.id,
            event_type=f"telemetry.{code}",
            severity="critical" if alert.get("level") == "critical" else "warning",
            title=f"{router_name}: {alert.get('message')}",
            message=str(alert.get("message") or ""),
            source="telemetry",
            data={"alert_code": code},
            fingerprint=f"{device.id}:telemetry:{code}",
            dedupe_seconds=300,
            config=config,
        )
    for code in {"memory", "wan", "stale", "load.high"} - active_codes:
        resolve_events(
            db,
            device_id=device.id,
            event_type=f"telemetry.{code}",
            title=f"{router_name}: состояние нормализовалось",
            message=f"Предупреждение {code} больше не наблюдается.",
            config=config,
        )
    db.commit()
    return {"status": "ok"}
