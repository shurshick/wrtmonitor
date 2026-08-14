from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from ..models import NetworkClient


MINIMUM_ONLINE_TTL_SECONDS = 30
MINIMUM_RECENT_TTL_SECONDS = 300


def _telemetry_interval(telemetry: dict[str, Any]) -> int:
    agent = telemetry.get("agent") or {}
    try:
        interval = int(agent.get("telemetry_interval_seconds") or 60)
    except (TypeError, ValueError):
        interval = 60
    return min(max(interval, 5), 3600)


def client_presence_ttl(telemetry: dict[str, Any]) -> timedelta:
    interval = _telemetry_interval(telemetry)
    return timedelta(seconds=max(MINIMUM_ONLINE_TTL_SECONDS, interval * 3))


def client_recent_ttl(telemetry: dict[str, Any]) -> timedelta:
    interval = _telemetry_interval(telemetry)
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
