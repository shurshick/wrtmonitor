from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from backend.app.services.telemetry import build_telemetry_history


def test_build_telemetry_history_calculates_rates_and_resources():
    started = datetime(2026, 7, 17, 10, 0, tzinfo=UTC)
    rows = [
        SimpleNamespace(
            created_at=started,
            payload={
                "system": {
                    "load": "0.15",
                    "memory": {"total_kb": 262144, "available_kb": 196608},
                },
                "traffic": {"rx_bytes": 1_000, "tx_bytes": 2_000},
                "clients": {"dhcp": {"leases": [{"mac": "00:11:22:33:44:55"}]}},
            },
        ),
        SimpleNamespace(
            created_at=started + timedelta(seconds=10),
            payload={
                "system": {
                    "load": "0.25",
                    "memory": {"total_kb": 262144, "available_kb": 131072},
                },
                "traffic": {"rx_bytes": 2_000, "tx_bytes": 2_500},
                "clients": {
                    "dhcp": {
                        "leases": [
                            {"mac": "00:11:22:33:44:55"},
                            {"mac": "00:11:22:33:44:66"},
                        ]
                    }
                },
            },
        ),
    ]

    points = build_telemetry_history(rows)

    assert points[0]["rx_bps"] == 0
    assert points[1]["rx_bps"] == 800
    assert points[1]["tx_bps"] == 400
    assert points[1]["memory_percent"] == 50.0
    assert points[1]["load_1m"] == 0.25
    assert points[1]["client_count"] == 2


def test_build_telemetry_history_treats_counter_reset_as_zero_rate():
    started = datetime(2026, 7, 17, 10, 0, tzinfo=UTC)
    rows = [
        SimpleNamespace(created_at=started, payload={"traffic": {"rx_bytes": 5000}}),
        SimpleNamespace(
            created_at=started + timedelta(seconds=5),
            payload={"traffic": {"rx_bytes": 100}},
        ),
    ]

    assert build_telemetry_history(rows)[1]["rx_bps"] == 0
