from datetime import UTC, datetime
from uuid import uuid4

from backend.app.models import EventRecord
from backend.app.services.command_validation import validate_command_payload
from backend.app.services.events import public_event


def test_existing_guest_network_can_be_toggled_without_resending_secret():
    assert validate_command_payload(
        "wifi.set_guest", {"enabled": True, "radio": "radio0"}
    ) == {"enabled": True, "radio": "radio0"}
    assert validate_command_payload("wifi.set_guest", {"enabled": False}) == {
        "enabled": False
    }


def test_technical_event_title_is_presented_in_plain_language():
    now = datetime.now(UTC)
    event = EventRecord(
        id=uuid4(),
        device_id=uuid4(),
        event_type="device.offline",
        severity="critical",
        source="server",
        title="device.offline",
        message="Агент не выходил на связь.",
        event_data={},
        fingerprint="device-offline",
        status="open",
        occurrence_count=1,
        occurred_at=now,
        last_occurred_at=now,
    )
    assert public_event(event)["title"] == "Роутер не отвечает"


def test_daily_actions_are_present_in_web_and_android_surfaces():
    web = open("backend/app/templates/partials/overview.html", encoding="utf-8").read()
    android = open(
        "android/app/src/main/java/ru/wrtmonitor/app/ui/screens/DeviceDetailScreen.kt",
        encoding="utf-8",
    ).read()
    for command in (
        "router.reboot",
        "wifi.set_enabled",
        "wifi.set_guest",
        "diagnostics.run",
    ):
        assert command in web
        assert command in android
    assert "section=clients" in web
    assert "onOpenClients" in android
