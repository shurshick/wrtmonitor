from datetime import UTC, datetime, timedelta
from uuid import uuid4

from backend.app.models import NetworkClient
from backend.app.services.client_registry import (
    apply_client_presence,
    client_presence_ttl,
    client_recent_ttl,
    effective_client_presence,
)
from backend.app.services.telemetry import normalize_clients_summary


def network_client(now: datetime, **overrides) -> NetworkClient:
    values = {
        "id": uuid4(),
        "device_id": uuid4(),
        "mac": "00:11:22:33:44:55",
        "online": False,
        "presence_state": "offline",
        "is_static": False,
        "policy": {},
        "first_seen_at": now,
        "last_seen_at": now,
        "updated_at": now,
    }
    values.update(overrides)
    return NetworkClient(**values)


def test_presence_windows_follow_agent_interval_with_sane_minimums():
    assert client_presence_ttl(
        {"agent": {"telemetry_interval_seconds": 5}}
    ) == timedelta(seconds=30)
    assert client_recent_ttl({"agent": {"telemetry_interval_seconds": 5}}) == timedelta(
        seconds=300
    )
    assert client_presence_ttl(
        {"agent": {"telemetry_interval_seconds": 60}}
    ) == timedelta(seconds=180)
    assert client_recent_ttl(
        {"agent": {"telemetry_interval_seconds": 60}}
    ) == timedelta(seconds=600)


def test_confirmed_client_degrades_to_recent_then_offline():
    now = datetime(2026, 7, 22, 10, 0, tzinfo=UTC)
    client = network_client(
        now,
        online=True,
        presence_state="online",
        online_until=now + timedelta(seconds=30),
        presence_expires_at=now + timedelta(minutes=5),
    )

    assert effective_client_presence(client, now + timedelta(seconds=29)) == "online"
    assert effective_client_presence(client, now + timedelta(seconds=31)) == "recent"
    assert effective_client_presence(client, now + timedelta(minutes=6)) == "offline"


def test_explicit_offline_evidence_wins_over_unexpired_confirmation():
    now = datetime(2026, 7, 22, 10, 0, tzinfo=UTC)
    client = network_client(
        now,
        online=False,
        presence_state="offline",
        online_until=now + timedelta(minutes=3),
        presence_expires_at=now + timedelta(minutes=10),
    )

    assert effective_client_presence(client, now) == "offline"


def test_repeated_stale_evidence_does_not_extend_recent_window():
    first_seen = datetime(2026, 7, 22, 10, 0, tzinfo=UTC)
    original_expiry = first_seen + timedelta(minutes=5)
    client = network_client(
        first_seen,
        online=False,
        presence_state="recent",
        presence_source="neighbour_stale",
        last_observed_at=first_seen,
        presence_expires_at=original_expiry,
    )

    apply_client_presence(
        client,
        "recent",
        "neighbour_stale",
        first_seen + timedelta(minutes=4),
        timedelta(seconds=30),
        timedelta(minutes=5),
    )

    assert client.presence_expires_at == original_expiry
    assert client.last_observed_at == first_seen
    assert (
        effective_client_presence(client, first_seen + timedelta(minutes=6))
        == "offline"
    )


def test_stale_neighbour_is_recent_but_not_online():
    summary = normalize_clients_summary(
        {
            "clients": {
                "neighbours": [
                    {
                        "mac": "00:11:22:33:44:55",
                        "ip": "192.168.31.42",
                        "state": "STALE",
                    }
                ]
            }
        }
    )

    assert summary["online_count"] == 0
    assert summary["recent_count"] == 1
    assert summary["items"][0]["presence_evidence"] == "recent"


def test_permanent_neighbour_is_inventory_only_not_presence_evidence():
    summary = normalize_clients_summary(
        {
            "clients": {
                "neighbours": [
                    {
                        "mac": "00:11:22:33:44:55",
                        "ip": "192.168.31.42",
                        "state": "PERMANENT",
                    }
                ]
            }
        }
    )

    assert summary["online_count"] == 0
    assert summary["recent_count"] == 0
    assert summary["items"][0]["presence_evidence"] == "unknown"


def test_wifi_station_confirms_presence_even_with_failed_neighbour():
    summary = normalize_clients_summary(
        {
            "clients": {
                "neighbours": [
                    {
                        "mac": "00:11:22:33:44:55",
                        "ip": "fe80::211:22ff:fe33:4455",
                        "state": "FAILED",
                    }
                ]
            },
            "wifi": {
                "stations": [
                    {
                        "interface": "phy0-ap0",
                        "clients": {"00:11:22:33:44:55": {"signal": -55}},
                    }
                ]
            },
        }
    )

    assert summary["online_count"] == 1
    assert summary["items"][0]["presence_source"] == "wifi_station"
