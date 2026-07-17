from uuid import uuid4

import pytest
from fastapi import HTTPException

from backend.app.services.config_transactions import (
    attach_transaction_metadata,
    build_command_preview,
    ensure_preflight_valid,
)
from backend.app.services.commands import validate_command_request


TELEMETRY = {
    "network": {
        "interfaces": [
            {
                "interface": "lan",
                "up": True,
                "proto": "static",
                "ipv4-address": [{"address": "192.168.1.1", "mask": 24}],
            },
            {
                "interface": "wan",
                "up": True,
                "proto": "dhcp",
                "ipv4-address": [{"address": "10.0.0.2", "mask": 24}],
            },
        ]
    },
    "wifi": {
        "available": True,
        "radios": [
            {
                "id": "radio0",
                "up": True,
                "channel": "6",
                "interfaces": [{"id": "default_radio0", "ssid": "Old SSID"}],
            }
        ],
    },
}


def test_transaction_metadata_is_attached_to_config_commands():
    command_id = uuid4()
    payload = attach_transaction_metadata(
        "network.set_lan",
        {"interface": "lan", "ip_address": "192.168.2.1", "netmask": "255.255.255.0"},
        command_id,
    )
    transaction = payload["_transaction"]
    assert transaction["id"] == str(command_id)
    assert transaction["configs"] == ["network"]
    assert transaction["connectivity_sensitive"] is True
    assert transaction["rollback_timeout_seconds"] == 90


def test_preview_contains_current_and_proposed_values():
    preview = build_command_preview(
        "wifi.set_ssid",
        {"iface": "default_radio0", "ssid": "New SSID"},
        TELEMETRY,
    )
    assert preview["can_apply"] is True
    assert preview["transactional"] is True
    ssid = next(change for change in preview["changes"] if change["field"] == "ssid")
    assert ssid == {"field": "ssid", "current": "Old SSID", "proposed": "New SSID"}
    assert preview["rollback_timeout_seconds"] == 90


def test_preview_masks_secrets():
    preview = build_command_preview(
        "wifi.set_password",
        {"iface": "default_radio0", "password": "new-secret-password"},
        TELEMETRY,
    )
    password = next(
        change for change in preview["changes"] if change["field"] == "password"
    )
    assert password["current"] is None
    assert password["proposed"] == "********"


@pytest.mark.parametrize(
    ("command_type", "payload"),
    [
        (
            "network.set_wan",
            {
                "interface": "wan",
                "protocol": "static",
                "ip_address": "10.0.0.2",
                "netmask": "255.255.255.0",
                "gateway": "10.0.1.1",
            },
        ),
        (
            "network.set_lan",
            {
                "interface": "lan",
                "ip_address": "192.168.2.0",
                "netmask": "255.255.255.0",
            },
        ),
        (
            "dhcp.set_pool",
            {"interface": "lan", "start": 200, "limit": 100, "leasetime": "12h"},
        ),
        (
            "firewall.set_port_forward",
            {
                "name": "outside-lan",
                "protocol": "tcp",
                "external_port": 443,
                "internal_ip": "192.168.2.50",
                "internal_port": 443,
            },
        ),
    ],
)
def test_preflight_rejects_dangerous_network_values(command_type, payload):
    with pytest.raises(HTTPException) as error:
        ensure_preflight_valid(command_type, payload, TELEMETRY)
    assert error.value.status_code == 409


def test_non_config_command_has_no_transaction():
    command_id = uuid4()
    assert attach_transaction_metadata("diagnostics.run", {}, command_id) == {}
    preview = build_command_preview("diagnostics.run", {}, TELEMETRY)
    assert preview["transactional"] is False
    assert preview["rollback_timeout_seconds"] is None


def test_old_agent_cannot_receive_unprotected_config_change():
    with pytest.raises(HTTPException) as error:
        validate_command_request(
            command_type="wifi.set_ssid",
            payload={"iface": "default_radio0", "ssid": "New SSID"},
            confirmed=True,
            device_supports=lambda capability: capability != "config.transaction",
        )
    assert error.value.status_code == 409
