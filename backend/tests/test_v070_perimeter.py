import pytest
from fastapi import HTTPException

from backend.app.services.commands import (
    public_command_payload,
    validate_command_payload,
)
from backend.app.services.config_transactions import CONFIG_TRANSACTION_SCOPES
from backend.app.services.telemetry import normalize_network_summary


def test_ipv6_multiwan_and_routes_are_normalized():
    assert validate_command_payload(
        "network.set_ipv6",
        {
            "interface": "lan",
            "enabled": True,
            "assignment_length": "64",
            "ra": "server",
            "dhcpv6": "server",
            "ndp": "disabled",
        },
    ) == {
        "interface": "lan",
        "enabled": True,
        "assignment_length": 64,
        "ra": "server",
        "dhcpv6": "server",
        "ndp": "disabled",
    }
    assert (
        validate_command_payload(
            "network.set_multiwan",
            {
                "enabled": True,
                "primary_interface": "wan",
                "secondary_interface": "wan2",
                "primary_metric": 10,
                "secondary_metric": 20,
            },
        )["secondary_interface"]
        == "wan2"
    )
    assert (
        validate_command_payload(
            "network.set_route",
            {
                "name": "office-v6",
                "interface": "wan6",
                "target": "2001:db8:42::/64",
                "gateway": "2001:db8::1",
                "metric": "15",
            },
        )["metric"]
        == 15
    )


@pytest.mark.parametrize(
    ("command_type", "payload"),
    [
        ("network.set_route", {"name": "bad", "target": "not-a-network"}),
        (
            "network.set_ipv6",
            {"interface": "lan", "enabled": True, "assignment_length": 80},
        ),
        (
            "firewall.set_rule",
            {"name": "bad", "src": "wan", "protocol": "shell", "target": "ACCEPT"},
        ),
    ],
)
def test_perimeter_validation_rejects_unsafe_values(command_type, payload):
    with pytest.raises(HTTPException) as error:
        validate_command_payload(command_type, payload)
    assert error.value.status_code == 400


def test_ddns_secret_is_masked_and_transactions_cover_perimeter():
    public = public_command_payload(
        "network.set_ddns",
        {"domain": "router.example.org", "password": "secret-token"},
    )
    assert public["password"] == "********"
    assert CONFIG_TRANSACTION_SCOPES["network.set_ipv6"] == ("network", "dhcp")
    assert CONFIG_TRANSACTION_SCOPES["network.set_upnp"] == ("upnpd", "firewall")
    assert CONFIG_TRANSACTION_SCOPES["firewall.set_rule"] == ("firewall",)


def test_perimeter_telemetry_is_normalized_for_interfaces_and_services():
    result = normalize_network_summary(
        {
            "network": {
                "interfaces": [
                    {
                        "interface": "wan6",
                        "up": True,
                        "proto": "dhcpv6",
                        "ipv6-address": [{"address": "2001:db8::2"}],
                    }
                ]
            },
            "perimeter": {
                "routes": [{"name": "office", "family": "ipv6"}],
                "firewall_forwardings": [{"src": "lan", "dest": "wan"}],
                "firewall_rules": [{"name": "Allow-DNS", "target": "ACCEPT"}],
                "mwan3": {"service": "running", "status": "online"},
                "ddns": {"service": "running", "services": [{"name": "home"}]},
                "upnp": {"service": "running", "mappings": ["TCP:443"]},
            },
        }
    )
    assert result["interfaces"][0]["ipv6"] == ["2001:db8::2"]
    assert result["firewall_forwardings"][0] == {"src": "lan", "dest": "wan"}
    assert result["upnp"]["mappings"] == ["TCP:443"]
