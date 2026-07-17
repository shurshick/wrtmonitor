from backend.app.services.commands import validate_command_payload
from backend.app.services.telemetry import (
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
