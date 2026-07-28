from backend.app.services.commands import (
    build_command_payload_from_web_form,
    validate_command_payload,
)
from backend.app.services.config_transactions import CONFIG_TRANSACTION_SCOPES
from backend.app.services.telemetry import (
    normalize_network_summary,
    normalize_vpn_summary,
)


def test_firewall_redirect_uses_actual_uci_section():
    payload = build_command_payload_from_web_form(
        "firewall.set_redirect",
        uci_section="@redirect[2]",
        name="camera",
        enabled="true",
        interface="wan",
        network="lan",
        protocol="tcp",
        external_port="8443",
        internal_ip="192.168.1.20",
        internal_port="443",
        hostname="DNAT",
    )
    assert payload["section"] == "@redirect[2]"
    assert payload["dest_ip"] == "192.168.1.20"
    assert CONFIG_TRANSACTION_SCOPES["firewall.set_redirect"] == ("firewall",)


def test_routes_and_vpn_policies_keep_actual_sections():
    route = build_command_payload_from_web_form(
        "network.set_route",
        uci_section="@route[1]",
        name="office",
        interface="wg0",
        ip_address="10.20.0.0/16",
        gateway="10.0.0.1",
    )
    policy = build_command_payload_from_web_form(
        "vpn.policy.set",
        uci_section="@policy[4]",
        name="office",
        interface="wg0",
        source="192.168.1.50",
        destination="10.20.0.0/16",
    )
    assert route["section"] == "@route[1]"
    assert policy["section"] == "@policy[4]"


def test_vpn_and_nat_observed_state_is_preserved():
    payload = {
        "network": {},
        "perimeter": {"firewall_redirects": [{"section": "@redirect[0]"}]},
        "vpn": {
            "wireguard": {
                "interfaces": [
                    {
                        "section": "wg0",
                        "name": "wg0",
                        "configured": True,
                        "enabled": True,
                        "runtime": False,
                        "addresses": ["10.0.0.1/24"],
                        "peers": [],
                    }
                ]
            },
            "openvpn": {"clients": []},
            "policy": {"policies": []},
        },
    }
    assert (
        normalize_network_summary(payload)["firewall_redirects"][0]["section"]
        == "@redirect[0]"
    )
    interface = normalize_vpn_summary(payload)["wireguard"]["interfaces"][0]
    assert interface["configured"] is True
    assert interface["runtime"] is False


def test_new_vpn_commands_validate():
    assert validate_command_payload(
        "vpn.wireguard.delete_interface", {"name": "wg0"}
    ) == {"name": "wg0"}
    assert (
        validate_command_payload(
            "vpn.openvpn.set_enabled", {"name": "office", "enabled": False}
        )["enabled"]
        is False
    )
    assert validate_command_payload(
        "vpn.openvpn.export_client", {"name": "office"}
    ) == {"name": "office"}
