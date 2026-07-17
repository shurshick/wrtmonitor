import pytest
from fastapi import HTTPException

from backend.app.services.commands import (
    build_command_payload_from_web_form,
    public_command_payload,
    validate_command_payload,
)
from backend.app.services.config_transactions import (
    CONFIG_TRANSACTION_SCOPES,
    SECRET_FIELDS,
)
from backend.app.services.telemetry import normalize_vpn_summary


WG_KEY = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="


def test_wireguard_interface_and_peer_are_normalized():
    interface = validate_command_payload(
        "vpn.wireguard.set_interface",
        {
            "name": "wg0",
            "enabled": True,
            "mode": "server",
            "addresses": ["10.7.0.1/24", "fd00:7::1/64"],
            "listen_port": "51820",
            "private_key": WG_KEY,
            "mtu": "1420",
        },
    )
    assert interface["listen_port"] == 51820
    assert interface["addresses"] == ["10.7.0.1/24", "fd00:7::1/64"]

    peer = validate_command_payload(
        "vpn.wireguard.set_peer",
        {
            "interface": "wg0",
            "name": "phone",
            "public_key": WG_KEY,
            "preshared_key": WG_KEY,
            "allowed_ips": ["10.7.0.2/32", "fd00:7::2/128"],
            "endpoint": "[2001:db8::10]:51820",
            "persistent_keepalive": "25",
            "route_allowed_ips": True,
        },
    )
    assert peer["endpoint"] == "[2001:db8::10]:51820"
    assert peer["persistent_keepalive"] == 25


@pytest.mark.parametrize(
    ("command_type", "payload"),
    [
        (
            "vpn.wireguard.set_interface",
            {"name": "wg0", "enabled": True, "addresses": ["bad-address"]},
        ),
        (
            "vpn.wireguard.set_peer",
            {
                "name": "peer",
                "public_key": "not-a-key",
                "allowed_ips": ["0.0.0.0/0"],
            },
        ),
        (
            "vpn.openvpn.set_client",
            {
                "name": "unsafe",
                "enabled": True,
                "config": "client\nremote vpn.example 1194\nup /bin/sh",
            },
        ),
        (
            "vpn.policy.set",
            {"name": "empty", "enabled": True, "interface": "wg0"},
        ),
    ],
)
def test_vpn_validation_rejects_unsafe_payloads(command_type, payload):
    with pytest.raises(HTTPException) as error:
        validate_command_payload(command_type, payload)
    assert error.value.status_code == 400


def test_openvpn_and_policy_payloads_are_normalized():
    openvpn = validate_command_payload(
        "vpn.openvpn.set_client",
        {
            "name": "office",
            "enabled": True,
            "config": "client\nremote vpn.example.org 1194\nproto udp\n",
        },
    )
    assert openvpn["config"].startswith("client\n")
    policy = validate_command_payload(
        "vpn.policy.set",
        {
            "name": "tv-via-vpn",
            "enabled": True,
            "interface": "wg0",
            "source": "192.168.1.50",
            "destination": "0.0.0.0/0",
            "protocol": "all",
        },
    )
    assert policy["source"] == "192.168.1.50"


def test_vpn_secrets_are_masked_and_transactions_are_declared():
    interface = public_command_payload(
        "vpn.wireguard.set_interface", {"private_key": WG_KEY}
    )
    peer = public_command_payload("vpn.wireguard.set_peer", {"preshared_key": WG_KEY})
    openvpn = public_command_payload(
        "vpn.openvpn.set_client", {"config": "client\nremote vpn.example 1194"}
    )
    assert interface["private_key"] == "********"
    assert peer["preshared_key"] == "********"
    assert openvpn["config"] == "********"
    assert {"private_key", "preshared_key", "config"} <= SECRET_FIELDS
    assert CONFIG_TRANSACTION_SCOPES["vpn.wireguard.set_peer"] == ("network",)
    assert CONFIG_TRANSACTION_SCOPES["vpn.openvpn.set_client"] == ("openvpn",)
    assert CONFIG_TRANSACTION_SCOPES["vpn.policy.set"] == ("pbr",)


def test_vpn_web_form_and_telemetry_summary():
    payload = build_command_payload_from_web_form(
        "vpn.wireguard.set_peer",
        interface="wg0",
        name="phone",
        public_key=WG_KEY,
        allowed_ips="10.7.0.2/32, fd00:7::2/128",
        endpoint="router.example.org:51820",
        internal_port="25",
    )
    assert payload["allowed_ips"] == ["10.7.0.2/32", "fd00:7::2/128"]

    summary = normalize_vpn_summary(
        {
            "vpn": {
                "wireguard": {
                    "interfaces": [
                        {
                            "name": "wg0",
                            "peers": [
                                {"rx_bytes": 100, "tx_bytes": 200},
                                {"rx_bytes": 50, "tx_bytes": 75},
                            ],
                        }
                    ]
                },
                "openvpn": {"service": "running", "clients": [{"name": "office"}]},
                "policy": {"service": "running", "policies": [{"name": "tv"}]},
            }
        }
    )
    assert summary["wireguard"]["interfaces"][0]["peer_count"] == 2
    assert summary["wireguard"]["interfaces"][0]["rx_bytes"] == 150
    assert summary["openvpn"]["service"] == "running"
