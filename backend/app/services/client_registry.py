from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

from fastapi import HTTPException
import pymanuf
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ..models import (
    ClientActivityEvent,
    ClientProfile,
    ClientTrafficSample,
    DeviceCommand,
    NetworkClient,
)
from .telemetry import normalize_clients_summary


WEEKDAYS = {"mon", "tue", "wed", "thu", "fri", "sat", "sun"}
TIME_PATTERN = re.compile(r"^(?:[01]\d|2[0-3]):[0-5]\d$")
CLIENT_TRAFFIC_RETENTION = 96
CLIENT_ACTIVITY_RETENTION = 200
MINIMUM_ONLINE_TTL_SECONDS = 30
MINIMUM_RECENT_TTL_SECONDS = 300


def client_presence_ttl(telemetry: dict[str, Any]) -> timedelta:
    agent = telemetry.get("agent") or {}
    try:
        interval = int(agent.get("telemetry_interval_seconds") or 60)
    except (TypeError, ValueError):
        interval = 60
    interval = min(max(interval, 5), 3600)
    return timedelta(seconds=max(MINIMUM_ONLINE_TTL_SECONDS, interval * 3))


def client_recent_ttl(telemetry: dict[str, Any]) -> timedelta:
    agent = telemetry.get("agent") or {}
    try:
        interval = int(agent.get("telemetry_interval_seconds") or 60)
    except (TypeError, ValueError):
        interval = 60
    interval = min(max(interval, 5), 3600)
    return timedelta(seconds=max(MINIMUM_RECENT_TTL_SECONDS, interval * 10))


def effective_client_presence(
    client: NetworkClient, now: datetime | None = None
) -> str:
    now = now or datetime.now(UTC)
    if client.presence_state == "offline":
        return "offline"
    if not client.presence_expires_at or now > client.presence_expires_at:
        return "offline"
    if client.online and client.online_until and now <= client.online_until:
        return "online"
    if client.presence_state in {"online", "recent"}:
        return "recent"
    return "offline"


def apply_client_presence(
    client: NetworkClient,
    evidence: str,
    source: str | None,
    now: datetime,
    online_ttl: timedelta,
    recent_ttl: timedelta,
) -> None:
    previous_presence_source = client.presence_source
    if evidence == "confirmed":
        client.online = True
        client.presence_state = "online"
        client.presence_source = source or "confirmed"
        client.last_observed_at = now
        client.last_confirmed_at = now
        client.last_seen_at = now
        client.online_until = now + online_ttl
        client.presence_expires_at = now + recent_ttl
    elif evidence == "recent":
        repeated_stale = previous_presence_source in {
            "neighbour_stale",
            "neighbour_grace",
        }
        still_confirmed = bool(client.online_until and now <= client.online_until)
        client.online = still_confirmed
        client.presence_state = "online" if still_confirmed else "recent"
        client.presence_source = (
            "neighbour_grace" if still_confirmed else source or "recent"
        )
        if not repeated_stale:
            client.last_observed_at = now
            client.presence_expires_at = now + recent_ttl
    elif evidence == "offline":
        client.online = False
        client.presence_state = "offline"
        client.presence_source = source
        client.last_observed_at = now
        client.online_until = None
        client.presence_expires_at = now


def normalize_mac(value: str) -> str:
    mac = value.strip().lower().replace("-", ":")
    if not re.fullmatch(r"(?:[0-9a-f]{2}:){5}[0-9a-f]{2}", mac):
        raise HTTPException(status_code=422, detail="Invalid client MAC address")
    return mac


def inferred_vendor(mac: str, reported: Any = None) -> str | None:
    if reported:
        return str(reported)[:160]
    first_octet = int(mac[:2], 16)
    if first_octet & 2:
        return "Private/randomized MAC"
    try:
        return pymanuf.lookup(mac) or None
    except (KeyError, TypeError, ValueError):
        return None


CLIENT_DEVICE_TYPES = {
    "phone",
    "tablet",
    "computer",
    "tv",
    "speaker",
    "camera",
    "printer",
    "storage",
    "router",
    "iot",
    "unknown",
}


def infer_device_type(*values: Any) -> str:
    identity = " ".join(str(value).lower() for value in values if value)
    rules = (
        ("tv", ("smart tv", "android tv", "television", "chromecast", "fire tv")),
        ("phone", ("phone", "iphone", "android", "redmi", "poco", "mobile")),
        ("tablet", ("tablet", "ipad", "tab ")),
        (
            "computer",
            (
                "desktop",
                "computer",
                "laptop",
                "notebook",
                "macbook",
                "windows",
                "workstation",
            ),
        ),
        (
            "speaker",
            ("speaker", "alexa", "echo dot", "homepod", "яндекс станц", "sberboom"),
        ),
        ("camera", ("camera", "cam ", "ipcam", "doorbell", "видеокамер")),
        ("printer", ("printer", "laserjet", "officejet", "pixma", "epson")),
        ("storage", ("nas", "synology", "qnap", "truenas")),
        ("router", ("router", "openwrt", "gateway", "access point")),
        (
            "iot",
            (
                "iot",
                "sensor",
                "socket",
                "plug",
                "bulb",
                "thermostat",
                "esp32",
                "esp8266",
            ),
        ),
    )
    for device_type, markers in rules:
        if any(marker in identity for marker in markers):
            return device_type
    return "unknown"


def validate_device_type(value: str | None) -> str:
    normalized = str(value or "unknown").strip().lower()
    if normalized not in CLIENT_DEVICE_TYPES:
        raise HTTPException(status_code=422, detail="Invalid client device type")
    return normalized


def record_client_activity(
    db: Session,
    client: NetworkClient,
    state: str,
    source: str | None,
    occurred_at: datetime,
) -> None:
    db.add(
        ClientActivityEvent(
            id=uuid4(),
            client_id=client.id,
            state=state,
            source=source,
            ip_address=client.ip_address,
            interface=client.interface,
            occurred_at=occurred_at,
        )
    )
    db.flush()
    retained_ids = (
        select(ClientActivityEvent.id)
        .where(ClientActivityEvent.client_id == client.id)
        .order_by(ClientActivityEvent.occurred_at.desc())
        .limit(CLIENT_ACTIVITY_RETENTION)
    )
    db.execute(
        delete(ClientActivityEvent).where(
            ClientActivityEvent.client_id == client.id,
            ClientActivityEvent.id.not_in(retained_ids),
        )
    )


def validate_client_policy(value: dict[str, Any] | None) -> dict[str, Any]:
    policy = dict(value or {})
    blocked = bool(policy.get("blocked", False))
    schedule = dict(policy.get("schedule") or {})
    weekdays = [str(day).lower() for day in schedule.get("weekdays") or []]
    if any(day not in WEEKDAYS for day in weekdays):
        raise HTTPException(status_code=422, detail="Invalid schedule weekday")
    for key in ("start", "stop"):
        if schedule.get(key) and not TIME_PATTERN.fullmatch(str(schedule[key])):
            raise HTTPException(status_code=422, detail=f"Invalid schedule {key} time")
    qos_input = dict(policy.get("qos") or {})
    qos: dict[str, Any] = {}
    for key in ("download_kbps", "upload_kbps"):
        try:
            value = int(qos_input.get(key) or 0)
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=422, detail=f"Invalid QoS {key}") from exc
        if value < 0 or value > 10_000_000:
            raise HTTPException(status_code=422, detail=f"Invalid QoS {key}")
        qos[key] = value
    priority = str(qos_input.get("priority") or "normal")
    if priority not in {"low", "normal", "high", "realtime"}:
        raise HTTPException(status_code=422, detail="Invalid QoS priority")
    qos["priority"] = priority
    dns = dict(policy.get("dns") or {})
    provider = str(dns.get("provider") or "none")
    if provider not in {"none", "cloudflare-security", "cloudflare-family"}:
        raise HTTPException(status_code=422, detail="Invalid client DNS policy")
    return {
        "blocked": blocked,
        "schedule": {
            "enabled": bool(schedule.get("enabled", False)),
            "weekdays": weekdays,
            "start": str(schedule.get("start") or ""),
            "stop": str(schedule.get("stop") or ""),
        },
        "qos": qos,
        "dns": {"provider": provider, "blocked_domains": []},
    }


def sync_client_inventory(
    db: Session, device_id: UUID, telemetry: dict[str, Any], now: datetime | None = None
) -> None:
    now = now or datetime.now(UTC)
    online_ttl = client_presence_ttl(telemetry)
    recent_ttl = client_recent_ttl(telemetry)
    observed_macs: set[str] = set()
    for item in normalize_clients_summary(telemetry).get("items") or []:
        try:
            mac = normalize_mac(str(item.get("mac") or ""))
        except HTTPException:
            continue
        observed_macs.add(mac)
        client = db.scalars(
            select(NetworkClient).where(
                NetworkClient.device_id == device_id, NetworkClient.mac == mac
            )
        ).first()
        created = client is None
        if client is None:
            client = NetworkClient(
                id=uuid4(),
                device_id=device_id,
                mac=mac,
                policy={},
                device_type="unknown",
                device_type_source="automatic",
                first_seen_at=now,
                last_seen_at=now,
                updated_at=now,
            )
            db.add(client)
            db.flush()
        previous_state = None if created else effective_client_presence(client, now)
        latest_sample = db.scalars(
            select(ClientTrafficSample)
            .where(ClientTrafficSample.client_id == client.id)
            .order_by(ClientTrafficSample.created_at.desc())
            .limit(1)
        ).first()
        client.hostname = item.get("hostname") or client.hostname
        client.ip_address = item.get("ip") or client.ip_address
        client.interface = item.get("interface") or client.interface
        client.vendor = inferred_vendor(mac, item.get("vendor")) or client.vendor
        if client.device_type_source != "user":
            client.device_type = infer_device_type(
                client.display_name,
                client.hostname,
                client.vendor,
            )
            client.device_type_source = "automatic"
        client.is_static = bool(item.get("is_static", False))
        client.updated_at = now
        try:
            rx_bytes = max(0, int(item.get("rx_bytes") or 0))
            tx_bytes = max(0, int(item.get("tx_bytes") or 0))
        except (TypeError, ValueError):
            rx_bytes = tx_bytes = 0
        has_traffic_counters = (
            item.get("rx_bytes") is not None or item.get("tx_bytes") is not None
        )
        traffic_increased = bool(
            has_traffic_counters
            and latest_sample
            and (rx_bytes > latest_sample.rx_bytes or tx_bytes > latest_sample.tx_bytes)
        )
        evidence = str(item.get("presence_evidence") or "unknown")
        source = item.get("presence_source")
        if traffic_increased:
            evidence = "confirmed"
            source = "traffic_activity"

        apply_client_presence(
            client,
            evidence,
            str(source) if source else None,
            now,
            online_ttl,
            recent_ttl,
        )
        current_state = effective_client_presence(client, now)
        if current_state != previous_state:
            record_client_activity(
                db, client, current_state, client.presence_source, now
            )
        if rx_bytes or tx_bytes:
            db.add(
                ClientTrafficSample(
                    id=uuid4(),
                    client_id=client.id,
                    rx_bytes=rx_bytes,
                    tx_bytes=tx_bytes,
                    created_at=now,
                )
            )
            db.flush()
            retained_ids = (
                select(ClientTrafficSample.id)
                .where(ClientTrafficSample.client_id == client.id)
                .order_by(ClientTrafficSample.created_at.desc())
                .limit(CLIENT_TRAFFIC_RETENTION)
            )
            db.execute(
                delete(ClientTrafficSample).where(
                    ClientTrafficSample.client_id == client.id,
                    ClientTrafficSample.id.not_in(retained_ids),
                )
            )

    missing_clients = db.scalars(
        select(NetworkClient).where(
            NetworkClient.device_id == device_id,
            NetworkClient.mac.not_in(observed_macs) if observed_macs else True,
        )
    ).all()
    for client in missing_clients:
        if (
            client.presence_state != "offline"
            and client.presence_expires_at
            and now > client.presence_expires_at
        ):
            apply_client_presence(
                client, "offline", "observation_expired", now, online_ttl, recent_ttl
            )
            record_client_activity(db, client, "offline", client.presence_source, now)


def effective_policy(db: Session, client: NetworkClient) -> dict[str, Any]:
    profile_policy: dict[str, Any] = {}
    if client.profile_id:
        profile = db.get(ClientProfile, client.profile_id)
        if profile and profile.device_id == client.device_id:
            profile_policy = profile.policy
    merged = dict(profile_policy or {})
    merged.update(client.policy or {})
    return validate_client_policy(merged)


def client_policy_application(db: Session, client: NetworkClient) -> dict[str, Any]:
    command = db.scalars(
        select(DeviceCommand)
        .where(
            DeviceCommand.device_id == client.device_id,
            DeviceCommand.command_type == "client.set_policy",
            DeviceCommand.payload["mac"].as_string() == client.mac,
        )
        .order_by(DeviceCommand.created_at.desc())
        .limit(1)
    ).first()
    if command is None:
        return {"state": "unconfigured", "status": None, "matches": False}

    result = command.result or {}
    observed_raw = result.get("observed") if isinstance(result, dict) else None
    observed = (
        validate_client_policy(observed_raw) if isinstance(observed_raw, dict) else None
    )
    desired = effective_policy(db, client)
    matches = bool(observed is not None and observed == desired)
    if command.status in {"queued", "sent", "running"}:
        state = "applying"
    elif command.status == "success" and matches:
        state = "applied"
    else:
        state = "error"
    error = command.last_error
    if not error and command.status == "success" and not matches:
        error = "Router did not confirm the requested policy"
    if not error and isinstance(result, dict):
        error = str(result.get("error") or result.get("message") or "") or None
    return {
        "state": state,
        "status": command.status,
        "command_id": str(command.id),
        "matches": matches,
        "error": error if state == "error" else None,
        "observed": observed,
        "updated_at": command.updated_at.isoformat(),
        "completed_at": command.completed_at.isoformat()
        if command.completed_at
        else None,
    }


def client_response(db: Session, client: NetworkClient) -> dict[str, Any]:
    now = datetime.now(UTC)
    presence_state = effective_client_presence(client, now)
    online = presence_state == "online"
    presence_source = client.presence_source
    if presence_state == "recent" and client.presence_state == "online":
        presence_source = "confirmation_expired"
    latest_sample = db.scalars(
        select(ClientTrafficSample)
        .where(ClientTrafficSample.client_id == client.id)
        .order_by(ClientTrafficSample.created_at.desc())
        .limit(1)
    ).first()
    activity = db.scalars(
        select(ClientActivityEvent)
        .where(ClientActivityEvent.client_id == client.id)
        .order_by(ClientActivityEvent.occurred_at.desc())
        .limit(5)
    ).all()
    traffic_is_current = bool(
        latest_sample
        and online
        and abs((client.last_seen_at - latest_sample.created_at).total_seconds()) <= 1
    )
    return {
        "id": str(client.id),
        "mac": client.mac,
        "display_name": client.display_name,
        "hostname": client.hostname,
        "vendor": client.vendor,
        "device_type": client.device_type or "unknown",
        "device_type_source": client.device_type_source or "automatic",
        "ip_address": client.ip_address,
        "interface": client.interface,
        "online": online,
        "presence_state": presence_state,
        "presence_source": presence_source,
        "last_observed_at": client.last_observed_at.isoformat()
        if client.last_observed_at
        else None,
        "last_confirmed_at": client.last_confirmed_at.isoformat()
        if client.last_confirmed_at
        else None,
        "presence_expires_at": client.presence_expires_at.isoformat()
        if client.presence_expires_at
        else None,
        "is_static": client.is_static,
        "profile_id": str(client.profile_id) if client.profile_id else None,
        "policy": client.policy or {},
        "effective_policy": effective_policy(db, client),
        "policy_application": client_policy_application(db, client),
        "first_seen_at": client.first_seen_at.isoformat(),
        "last_seen_at": client.last_seen_at.isoformat(),
        "traffic": {
            "rx_bytes": latest_sample.rx_bytes,
            "tx_bytes": latest_sample.tx_bytes,
            "created_at": latest_sample.created_at.isoformat(),
        }
        if traffic_is_current
        else None,
        "recent_activity": [
            {
                "state": event.state,
                "source": event.source,
                "ip_address": event.ip_address,
                "interface": event.interface,
                "occurred_at": event.occurred_at.isoformat(),
            }
            for event in activity
        ],
    }


def client_inventory_summary(db: Session, device_id: UUID) -> dict[str, Any]:
    clients = db.scalars(
        select(NetworkClient)
        .where(NetworkClient.device_id == device_id)
        .order_by(NetworkClient.last_seen_at.desc())
    ).all()
    items = [client_response(db, client) for client in clients]
    rank = {"online": 0, "recent": 1, "offline": 2}
    items.sort(
        key=lambda item: (
            rank.get(str(item.get("presence_state")), 3),
            str(item.get("display_name") or item.get("hostname") or item.get("mac")),
        )
    )
    return {
        "count": len(items),
        "online_count": sum(1 for item in items if item["presence_state"] == "online"),
        "recent_count": sum(1 for item in items if item["presence_state"] == "recent"),
        "offline_count": sum(
            1 for item in items if item["presence_state"] == "offline"
        ),
        "items": items,
    }
