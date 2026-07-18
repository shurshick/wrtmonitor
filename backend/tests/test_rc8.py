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


def test_wan_and_guest_passwords_are_masked():
    assert public_command_payload(
        "network.set_wan",
        {"protocol": "pppoe", "username": "owner", "password": "secret"},
    ) == {"protocol": "pppoe", "username": "owner", "password": "********"}
    assert (
        public_command_payload(
            "wifi.set_guest",
            {"enabled": True, "ssid": "Guest", "password": "secret-pass"},
        )["password"]
        == "********"
    )


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


def test_wan_and_lan_management_payloads_are_normalized():
    assert validate_command_payload(
        "network.set_wan",
        {
            "interface": "wan",
            "protocol": "static",
            "ip_address": "192.0.2.2",
            "netmask": "255.255.255.0",
            "gateway": "192.0.2.1",
            "dns": "1.1.1.1, 8.8.8.8",
            "mtu": "1500",
        },
    ) == {
        "interface": "wan",
        "protocol": "static",
        "ip_address": "192.0.2.2",
        "netmask": "255.255.255.0",
        "gateway": "192.0.2.1",
        "dns": ["1.1.1.1", "8.8.8.8"],
        "mtu": 1500,
    }
    assert (
        validate_command_payload(
            "network.set_lan",
            {"ip_address": "192.168.10.1", "netmask": "255.255.255.0"},
        )["interface"]
        == "lan"
    )


def test_router_management_rejects_invalid_high_risk_payloads():
    invalid = (
        ("network.set_wan", {"protocol": "shell"}),
        (
            "firewall.set_port_forward",
            {
                "name": "bad;reboot",
                "protocol": "tcp",
                "external_port": 80,
                "internal_ip": "192.168.1.2",
                "internal_port": 80,
            },
        ),
        ("dhcp.set_pool", {"start": 0, "limit": 150, "leasetime": "12h"}),
        ("client.set_blocked", {"mac": "not-a-mac", "blocked": True}),
    )
    for command_type, payload in invalid:
        try:
            validate_command_payload(command_type, payload)
        except Exception as exc:
            assert exc.status_code == 400
        else:
            raise AssertionError(f"Expected {command_type} payload to be rejected")


def test_guest_wifi_and_time_management_payloads():
    assert (
        validate_command_payload(
            "wifi.set_guest",
            {
                "enabled": True,
                "ssid": "Guests",
                "password": "strong-password",
                "radio": "radio0",
            },
        )["ssid"]
        == "Guests"
    )
    assert validate_command_payload(
        "system.set_timezone", {"zonename": "Europe/Moscow", "timezone": "MSK-3"}
    ) == {"zonename": "Europe/Moscow", "timezone": "MSK-3"}
    assert validate_command_payload(
        "system.set_ntp",
        {"enabled": True, "servers": "0.openwrt.pool.ntp.org, 1.openwrt.pool.ntp.org"},
    )["servers"] == ["0.openwrt.pool.ntp.org", "1.openwrt.pool.ntp.org"]


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
        for filename in (
            "clients.html",
            "wifi.html",
            "network.html",
            "rules.html",
            "system.html",
        )
    )
    for command_type in (
        "dhcp.set_lease",
        "dhcp.delete_lease",
        "wifi.set_radio",
        "network.interface_restart",
        "network.restart",
        "system.set_hostname",
        "system.restart_service",
    ):
        assert f'value="{command_type}"' in content


def test_web_ui_separates_internet_rules_and_vpn_workspaces():
    templates_dir = Path(__file__).resolve().parents[1] / "app" / "templates"
    device_detail = (templates_dir / "device_detail.html").read_text(encoding="utf-8")
    internet = (templates_dir / "partials" / "network.html").read_text(encoding="utf-8")
    rules = (templates_dir / "partials" / "rules.html").read_text(encoding="utf-8")

    assert "section=rules" in device_detail
    assert "section=vpn" in device_detail
    for command_type in (
        "firewall.set_port_forward",
        "firewall.set_rule",
        "firewall.set_zone",
        "network.set_route",
        "network.set_upnp",
    ):
        assert f'value="{command_type}"' in rules
        assert f'value="{command_type}"' not in internet


def test_web_ui_management_sections_are_collapsed_by_default():
    templates_dir = (
        Path(__file__).resolve().parents[1] / "app" / "templates" / "partials"
    )
    rules = (templates_dir / "rules.html").read_text(encoding="utf-8")
    system = (templates_dir / "system.html").read_text(encoding="utf-8")

    assert '<details class="settings-panel card" open>' not in rules
    assert "<strong>Межсетевой экран</strong>" in rules
    assert "<strong>Зоны и транзит</strong>" in rules

    for title in ("Идентификация", "Службы", "Дата и время"):
        assert f"<strong>{title}</strong>" in system
    assert '<details class="settings-panel card section">' in system
    assert '<details class="settings-panel card">' in system
    assert '<details class="settings-panel card" open>' not in system
