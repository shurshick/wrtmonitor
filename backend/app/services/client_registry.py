from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from fastapi import HTTPException
import pymanuf
from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from ..models import ClientProfile, ClientTrafficSample, NetworkClient
from .telemetry import normalize_clients_summary


WEEKDAYS = {"mon", "tue", "wed", "thu", "fri", "sat", "sun"}
TIME_PATTERN = re.compile(r"^(?:[01]\d|2[0-3]):[0-5]\d$")
CLIENT_TRAFFIC_RETENTION = 96
ONLINE_CLIENT_STATES = {
    "REACHABLE",
    "STALE",
    "DELAY",
    "PROBE",
    "PERMANENT",
    "NOARP",
    "WIFI",
}


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
    qos = dict(policy.get("qos") or {})
    for key in ("download_kbps", "upload_kbps"):
        try:
            value = int(qos.get(key) or 0)
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=422, detail=f"Invalid QoS {key}") from exc
        if value < 0 or value > 10_000_000:
            raise HTTPException(status_code=422, detail=f"Invalid QoS {key}")
        qos[key] = value
    priority = str(qos.get("priority") or "normal")
    if priority not in {"low", "normal", "high", "realtime"}:
        raise HTTPException(status_code=422, detail="Invalid QoS priority")
    qos["priority"] = priority
    return {
        "blocked": blocked,
        "schedule": {
            "enabled": bool(schedule.get("enabled", False)),
            "weekdays": weekdays,
            "start": str(schedule.get("start") or ""),
            "stop": str(schedule.get("stop") or ""),
        },
        "qos": qos,
    }


def sync_client_inventory(
    db: Session, device_id: UUID, telemetry: dict[str, Any], now: datetime | None = None
) -> None:
    now = now or datetime.now(UTC)
    db.execute(
        update(NetworkClient)
        .where(NetworkClient.device_id == device_id)
        .values(online=False, updated_at=now)
    )
    for item in normalize_clients_summary(telemetry).get("items") or []:
        try:
            mac = normalize_mac(str(item.get("mac") or ""))
        except HTTPException:
            continue
        client = db.scalars(
            select(NetworkClient).where(
                NetworkClient.device_id == device_id, NetworkClient.mac == mac
            )
        ).first()
        if client is None:
            client = NetworkClient(
                id=uuid4(),
                device_id=device_id,
                mac=mac,
                policy={},
                first_seen_at=now,
                last_seen_at=now,
                updated_at=now,
            )
            db.add(client)
        client.hostname = item.get("hostname") or client.hostname
        client.ip_address = item.get("ip") or client.ip_address
        client.interface = item.get("interface") or client.interface
        client.vendor = inferred_vendor(mac, item.get("vendor")) or client.vendor
        client.online = str(item.get("state") or "").upper() in ONLINE_CLIENT_STATES
        client.is_static = bool(item.get("is_static", False))
        if client.online:
            client.last_seen_at = now
        client.updated_at = now
        try:
            rx_bytes = max(0, int(item.get("rx_bytes") or 0))
            tx_bytes = max(0, int(item.get("tx_bytes") or 0))
        except (TypeError, ValueError):
            rx_bytes = tx_bytes = 0
        if rx_bytes or tx_bytes:
            db.flush()
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


def effective_policy(db: Session, client: NetworkClient) -> dict[str, Any]:
    profile_policy: dict[str, Any] = {}
    if client.profile_id:
        profile = db.get(ClientProfile, client.profile_id)
        if profile and profile.device_id == client.device_id:
            profile_policy = profile.policy
    merged = dict(profile_policy or {})
    merged.update(client.policy or {})
    return validate_client_policy(merged)


def client_response(db: Session, client: NetworkClient) -> dict[str, Any]:
    latest_sample = db.scalars(
        select(ClientTrafficSample)
        .where(ClientTrafficSample.client_id == client.id)
        .order_by(ClientTrafficSample.created_at.desc())
        .limit(1)
    ).first()
    return {
        "id": str(client.id),
        "mac": client.mac,
        "display_name": client.display_name,
        "hostname": client.hostname,
        "vendor": client.vendor,
        "ip_address": client.ip_address,
        "interface": client.interface,
        "online": client.online,
        "is_static": client.is_static,
        "profile_id": str(client.profile_id) if client.profile_id else None,
        "policy": client.policy or {},
        "effective_policy": effective_policy(db, client),
        "first_seen_at": client.first_seen_at.isoformat(),
        "last_seen_at": client.last_seen_at.isoformat(),
        "traffic": {
            "rx_bytes": latest_sample.rx_bytes,
            "tx_bytes": latest_sample.tx_bytes,
            "created_at": latest_sample.created_at.isoformat(),
        }
        if latest_sample
        else None,
    }
