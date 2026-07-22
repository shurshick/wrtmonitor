import pytest
from fastapi import HTTPException

from backend.app.services.client_registry import inferred_vendor, validate_client_policy
from backend.app.services.commands import validate_command_payload
from backend.app.services.config_transactions import build_command_preview
from backend.app.services.telemetry import normalize_clients_summary


def test_client_policy_normalizes_schedule_and_qos():
    policy = validate_client_policy(
        {
            "blocked": False,
            "schedule": {
                "enabled": True,
                "weekdays": ["mon", "fri"],
                "start": "22:00",
                "stop": "07:00",
            },
            "qos": {"priority": "high", "download_kbps": "50000"},
        }
    )
    assert policy["schedule"]["weekdays"] == ["mon", "fri"]
    assert policy["qos"] == {
        "priority": "high",
        "download_kbps": 50000,
        "upload_kbps": 0,
    }


@pytest.mark.parametrize(
    "policy",
    [
        {"schedule": {"weekdays": ["holiday"]}},
        {"schedule": {"start": "25:00"}},
        {"qos": {"priority": "magic"}},
        {"qos": {"download_kbps": "fast"}},
    ],
)
def test_client_policy_rejects_invalid_values(policy):
    with pytest.raises(HTTPException):
        validate_client_policy(policy)


def test_sqm_payload_is_validated_and_transactional():
    payload = validate_command_payload(
        "qos.set_sqm",
        {
            "enabled": True,
            "interface": "pppoe-wan",
            "download_kbps": "90000",
            "upload_kbps": "18000",
        },
    )
    assert payload["qdisc"] == "cake"
    assert payload["script"] == "piece_of_cake.qos"
    preview = build_command_preview("qos.set_sqm", payload)
    assert preview["transactional"] is True
    assert preview["configs"] == ["sqm"]


def test_client_normalization_preserves_vendor_and_traffic_counters():
    summary = normalize_clients_summary(
        {
            "clients": {
                "neighbours": [
                    {
                        "mac": "00:11:22:33:44:55",
                        "ip": "192.168.1.42",
                        "state": "REACHABLE",
                    },
                    {
                        "mac": "00:11:22:33:44:55",
                        "vendor": "Example Corp",
                        "rx_bytes": 1234,
                        "tx_bytes": 5678,
                    },
                ]
            }
        }
    )
    assert summary["count"] == 1
    assert summary["items"][0]["vendor"] == "Example Corp"
    assert summary["items"][0]["rx_bytes"] == 1234
    assert summary["items"][0]["tx_bytes"] == 5678


def test_client_normalization_marks_wifi_station_online_and_keeps_ipv4():
    summary = normalize_clients_summary(
        {
            "clients": {
                "dhcp": {
                    "leases": [
                        {
                            "mac": "00:11:22:33:44:55",
                            "ip": "192.168.31.42",
                            "hostname": "phone",
                        }
                    ]
                }
            },
            "wifi": {
                "stations": [
                    {
                        "interface": "phy0-ap0",
                        "ssid": "HomeNET",
                        "band": "5g",
                        "clients": {"00:11:22:33:44:55": {"signal": -51}},
                    }
                ]
            },
        }
    )
    item = summary["items"][0]
    assert item["ip"] == "192.168.31.42"
    assert item["state"] == "wifi"
    assert item["ssid"] == "HomeNET"
    assert item["band"] == "5g"
    assert summary["online_count"] == 1


def test_client_normalization_does_not_let_failed_ipv6_hide_reachable_ipv4():
    summary = normalize_clients_summary(
        {
            "clients": {
                "neighbours": [
                    {
                        "mac": "00:11:22:33:44:55",
                        "ip": "192.168.31.42",
                        "state": "REACHABLE",
                    },
                    {
                        "mac": "00:11:22:33:44:55",
                        "ip": "fe80::211:22ff:fe33:4455",
                        "state": "FAILED",
                    },
                ]
            }
        }
    )
    assert summary["items"][0]["state"] == "REACHABLE"
    assert summary["online_count"] == 1


def test_client_normalization_does_not_count_saved_dhcp_lease_as_online():
    summary = normalize_clients_summary(
        {
            "clients": {
                "dhcp": {
                    "leases": [
                        {
                            "mac": "00:11:22:33:44:55",
                            "ip": "192.168.31.42",
                            "hostname": "offline-phone",
                        }
                    ]
                }
            }
        }
    )
    assert summary["count"] == 1
    assert summary["online_count"] == 0


def test_vendor_lookup_uses_bundled_oui_database_and_handles_private_macs():
    assert inferred_vendor("bc:ee:7b:00:00:00") == "ASUSTek COMPUTER INC."
    assert inferred_vendor("02:11:22:33:44:55") == "Private/randomized MAC"
