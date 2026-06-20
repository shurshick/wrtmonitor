from datetime import timedelta
from uuid import uuid4

from backend.app.services.commands import (
    create_device_command,
    expire_old_commands,
    now_utc,
)
from backend.app.services.telemetry import build_telemetry_summary
from backend.app.web.csrf import generate_csrf_token, verify_csrf_token


def test_csrf_is_bound_to_session_and_secret():
    token = generate_csrf_token("session-a", "secret" * 8)
    assert verify_csrf_token("session-a", token, "secret" * 8)
    assert not verify_csrf_token("session-b", token, "secret" * 8)
    assert not verify_csrf_token("session-a", "", "secret" * 8)


def test_telemetry_summary_handles_missing_wifi():
    summary = build_telemetry_summary(
        {"system": {"uptime": 5, "memory": {"total_kb": 2048}}}
    )
    assert summary["wifi_available"] is False
    assert summary["wifi_radio_count"] == 0
    assert summary["memory_total_mb"] == 2


def test_create_command_has_expiry():
    class FakeSession:
        def __init__(self):
            self.item = None

        def add(self, item):
            self.item = item

    db = FakeSession()
    command = create_device_command(
        db,
        device_id=uuid4(),
        command_type="wifi.status",
        payload={},
        created_by=None,
        source="api",
    )
    assert command.status == "queued"
    assert command.expires_at and command.expires_at > command.created_at
    assert db.item is command
