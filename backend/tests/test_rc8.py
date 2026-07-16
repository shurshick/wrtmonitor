from datetime import UTC, datetime
from uuid import uuid4
from pathlib import Path

from fastapi.testclient import TestClient

from backend.app.api import commands as commands_api
from backend.app.api import devices as devices_api
from backend.app.main import app
from backend.app.db import get_db
from backend.app.models import Device, DeviceCommand, DeviceTelemetry
from backend.app.services.auth import current_user
from backend.app.services.commands import (
    ALLOWED_COMMANDS,
    COMMAND_REGISTRY,
    public_command_payload,
    validate_command_payload,
)
from backend.app.config import APP_VERSION
from backend.app.services.devices import get_latest_agent_capabilities
from backend.app.services.telemetry import (
    normalize_clients_summary,
    normalize_system_summary,
)


def test_allowed_commands_derived_from_registry():
    assert ALLOWED_COMMANDS == set(COMMAND_REGISTRY)


def test_wifi_password_payload_is_masked():
    payload = public_command_payload(
        "wifi.set_password",
        {"password": "secret-pass", "key": "secret-pass", "iface": "@wifi-iface[0]"},
    )
    assert payload["password"] == "********"
    assert payload["key"] == "********"
    assert payload["iface"] == "@wifi-iface[0]"


def test_wifi_ssid_validation_rejects_control_chars():
    try:
        validate_command_payload("wifi.set_ssid", {"ssid": "bad\nssid"})
    except Exception as exc:  # HTTPException without importing FastAPI here
        assert "control characters" in str(exc.detail)
    else:
        raise AssertionError("Expected validation error for control chars")


def test_wifi_password_validation_rejects_short_password():
    try:
        validate_command_payload("wifi.set_password", {"password": "short"})
    except Exception as exc:
        assert "8..63" in str(exc.detail)
    else:
        raise AssertionError("Expected validation error for short password")


def test_agent_interval_validation_rejects_values_below_minimum():
    try:
        validate_command_payload("agent.set_interval", {"interval_seconds": 4})
    except Exception as exc:
        assert "not less than 5" in str(exc.detail)
    else:
        raise AssertionError("Expected validation error for short interval")


def test_agent_interval_validation_accepts_integer_strings():
    payload = validate_command_payload("agent.set_interval", {"interval_seconds": "15"})
    assert payload == {"interval_seconds": 15}


def test_wifi_channel_and_country_validation():
    assert validate_command_payload(
        "wifi.set_channel", {"radio": "radio0", "channel": "36"}
    ) == {"radio": "radio0", "channel": "36"}
    assert validate_command_payload(
        "wifi.set_country", {"radio": "radio0", "country": "ru"}
    ) == {"radio": "radio0", "country": "RU"}


def test_network_and_service_allowlists_reject_shell_input():
    for command_type, payload in (
        ("network.interface_restart", {"interface": "wan; reboot"}),
        ("system.restart_service", {"service": "dropbear"}),
    ):
        try:
            validate_command_payload(command_type, payload)
        except Exception as exc:
            assert exc.status_code == 400
        else:
            raise AssertionError("Expected command payload to be rejected")


def test_dhcp_lease_validation_normalizes_mac_and_ipv4():
    assert validate_command_payload(
        "dhcp.set_lease",
        {"hostname": "printer", "mac": "AA-BB-CC-DD-EE-FF", "ip": "192.168.1.50"},
    ) == {
        "hostname": "printer",
        "mac": "aa:bb:cc:dd:ee:ff",
        "ip": "192.168.1.50",
    }


def test_clients_and_system_telemetry_are_normalized():
    payload = {
        "clients": {
            "dhcp": {
                "leases": [
                    {
                        "mac": "AA:BB:CC:DD:EE:FF",
                        "ip": "192.168.1.50",
                        "hostname": "printer",
                    }
                ]
            },
            "neighbours": [
                {
                    "mac": "aa:bb:cc:dd:ee:ff",
                    "ip": "192.168.1.50",
                    "interface": "br-lan",
                    "state": "REACHABLE",
                }
            ],
        },
        "system": {
            "hostname": "router",
            "kernel": "6.6.1",
            "conntrack": {"count": 10, "max": 16384},
            "services": {"dnsmasq": "running"},
        },
    }
    clients = normalize_clients_summary(payload)
    assert clients["count"] == 1
    assert clients["items"][0]["source"] == "dhcp+neighbour"
    assert clients["items"][0]["interface"] == "br-lan"
    system = normalize_system_summary(payload)
    assert system["hostname"] == "router"
    assert system["conntrack_count"] == 10
    assert system["services"]["dnsmasq"] == "running"


def test_get_latest_agent_capabilities_returns_mapping():
    device_id = uuid4()

    class FakeScalars:
        def __init__(self, item):
            self.item = item

        def first(self):
            return self.item

    class FakeSession:
        def scalars(self, statement):
            return FakeScalars(
                DeviceTelemetry(
                    id=uuid4(),
                    device_id=device_id,
                    payload={"agent": {"capabilities": {"wifi.set_password": True}}},
                    created_at=datetime.now(UTC),
                )
            )

    capabilities = get_latest_agent_capabilities(FakeSession(), device_id)
    assert capabilities == {"wifi.set_password": True}


def test_device_agent_endpoint_returns_normalized_status(monkeypatch):
    device = Device(
        id=uuid4(),
        name="HomeRouter",
        hostname="OpenWrt",
        model="VirtualBox",
        firmware="OpenWrt",
        token_hash="token",
        status="online",
        last_seen_at=None,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    class FakeSession:
        pass

    def fake_db():
        yield FakeSession()

    monkeypatch.setattr(
        devices_api, "get_user_device_or_404", lambda db, user, device_id: device
    )
    monkeypatch.setattr(
        devices_api,
        "get_latest_agent_status",
        lambda db, device_id: {
            "version": APP_VERSION,
            "status": "running",
            "telemetry_interval_seconds": 15,
            "capabilities": {"wifi.set_password": True},
        },
    )
    app.dependency_overrides[get_db] = fake_db
    app.dependency_overrides[current_user] = lambda: object()
    client = TestClient(app)
    try:
        response = client.get(
            f"/api/v1/devices/{device.id}/agent",
            headers={"Authorization": "Bearer token"},
        )
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 200
    assert response.json()["version"] == APP_VERSION
    assert response.json()["telemetry_interval_seconds"] == 15
    assert response.json()["capabilities"]["wifi.set_password"] is True


def test_commands_api_lists_risk_and_capability(monkeypatch):
    command = DeviceCommand(
        id=uuid4(),
        device_id=uuid4(),
        command_type="wifi.set_password",
        payload={"password": "secret-pass"},
        status="queued",
        result=None,
        created_by=None,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        picked_at=None,
        completed_at=None,
        expires_at=datetime.now(UTC),
        retry_count=0,
        last_error=None,
        source="api",
    )

    class FakeScalars:
        def __init__(self, items):
            self.items = items

        def all(self):
            return self.items

    class FakeSession:
        def execute(self, statement):
            class FakeResult:
                rowcount = 0

            return FakeResult()

        def scalars(self, statement):
            return FakeScalars([command])

        def commit(self):
            return None

    def fake_db():
        yield FakeSession()

    monkeypatch.setattr(
        commands_api, "get_user_device_or_404", lambda db, user, device_id: object()
    )
    app.dependency_overrides[get_db] = fake_db
    app.dependency_overrides[current_user] = lambda: object()
    client = TestClient(app)
    try:
        response = client.get(
            f"/api/v1/devices/{command.device_id}/commands",
            headers={"Authorization": "Bearer token"},
        )
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 200
    body = response.json()[0]
    assert body["risk_level"] == "level_3_reversible_config"
    assert body["capability"] == "wifi.set_password"
    assert body["payload"]["password"] == "********"


def test_web_ui_templates_expose_v2_management_controls():
    templates_dir = (
        Path(__file__).resolve().parents[1] / "app" / "templates" / "partials"
    )
    content = "\n".join(
        (templates_dir / filename).read_text(encoding="utf-8")
        for filename in ("clients.html", "wifi.html", "network.html", "system.html")
    )
    for command_type in (
        "dhcp.set_lease",
        "dhcp.delete_lease",
        "wifi.set_channel",
        "wifi.set_country",
        "network.interface_restart",
        "network.restart",
        "system.set_hostname",
        "system.restart_service",
    ):
        assert f'value="{command_type}"' in content
