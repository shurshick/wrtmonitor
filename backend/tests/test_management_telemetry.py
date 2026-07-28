from backend.app.services.commands import validate_command_payload
from backend.app.services.telemetry import (
    normalize_clients_summary,
    normalize_network_summary,
    normalize_system_summary,
)


def test_current_agent_network_format_preserves_real_lan_configuration():
    summary = normalize_network_summary(
        {
            "network": {
                "interfaces": [
                    {
                        "interface": "lan",
                        "up": True,
                        "proto": "static",
                        "device": "br-lan",
                        "ipv4": ["192.168.31.1"],
                        "ipv4_details": [
                            {"address": "192.168.31.1", "prefix_length": 24}
                        ],
                        "ipv6": ["fd00::1"],
                        "ip6assign": "64",
                        "ip6hint": "a",
                        "gateway": "192.168.31.254",
                        "dns": ["192.168.31.1"],
                    }
                ]
            }
        }
    )

    lan = summary["interfaces"][0]
    assert lan["ipv4"] == ["192.168.31.1"]
    assert lan["netmask"] == "255.255.255.0"
    assert lan["ipv4_details"] == [
        {
            "address": "192.168.31.1",
            "prefix_length": 24,
            "netmask": "255.255.255.0",
        }
    ]
    assert lan["ipv6"] == ["fd00::1"]
    assert lan["ip6assign"] == "64"
    assert lan["ip6hint"] == "a"
    assert lan["gateway"] == "192.168.31.254"
    assert lan["dns"] == ["192.168.31.1"]


def test_legacy_ubus_network_format_still_derives_netmask():
    summary = normalize_network_summary(
        {
            "network": {
                "interface": [
                    {
                        "interface": "lan",
                        "ipv4-address": [{"address": "192.168.31.1", "mask": 24}],
                    }
                ]
            }
        }
    )

    assert summary["interfaces"][0]["netmask"] == "255.255.255.0"


def test_network_topology_is_preserved_for_management_clients():
    topology = {
        "segments": [
            {
                "name": "lan",
                "proto": "static",
                "device": "br-lan",
                "bridge_section": "@device[0]",
                "ip_address": "192.168.31.1",
                "netmask": "255.255.255.0",
                "policy": "trusted",
                "enabled": True,
                "dhcp": {"enabled": True, "start": "100", "limit": "100"},
            }
        ],
        "bridges": [
            {"section": "@device[0]", "name": "br-lan", "ports": ["lan1", "lan2"]}
        ],
        "vlans": [
            {
                "section": "@bridge-vlan[0]",
                "device": "br-lan",
                "vlan_id": 10,
                "ports": ["lan1:u*", "lan2:t"],
            }
        ],
    }

    summary = normalize_network_summary({"network": {"topology": topology}})

    assert summary["topology"] == topology
    assert summary["topology"]["segments"][0]["bridge_section"] == "@device[0]"


def test_nlbw_source_can_be_ready_before_first_non_zero_counter():
    summary = normalize_clients_summary(
        {
            "clients": {
                "traffic": {
                    "available": True,
                    "status": "ready",
                    "installed": True,
                    "service": "running",
                    "records": 0,
                    "recovery_attempted": True,
                },
                "neighbours": [],
                "dhcp": {"leases": [], "static_leases": []},
            }
        }
    )

    assert summary["traffic_available"] is True
    assert summary["traffic_status"] == "ready"
    assert summary["traffic_diagnostics"] == {
        "installed": True,
        "service": "running",
        "records": 0,
        "recovery_attempted": True,
        "error": "",
    }


def test_time_configuration_is_normalized_without_ui_defaults():
    summary = normalize_system_summary(
        {
            "system": {
                "time": {
                    "zonename": "Asia/Yekaterinburg",
                    "timezone": "<+05>-5",
                    "ntp_enabled": True,
                    "ntp_servers": ["0.openwrt.pool.ntp.org"],
                }
            }
        }
    )

    assert summary["zonename"] == "Asia/Yekaterinburg"
    assert summary["timezone"] == "<+05>-5"
    assert summary["ntp_enabled"] is True
    assert summary["ntp_servers"] == ["0.openwrt.pool.ntp.org"]


def test_timezone_command_resolves_posix_value_from_catalog():
    assert validate_command_payload(
        "system.set_timezone", {"zonename": "Asia/Yekaterinburg"}
    ) == {"zonename": "Asia/Yekaterinburg", "timezone": "<+05>-5"}
