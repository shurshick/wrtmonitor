from pathlib import Path

import pytest
from fastapi import HTTPException

from backend.app.services.commands import (
    build_command_payload_from_web_form,
    validate_command_payload,
)
from backend.app.services.telemetry import normalize_wifi_summary


def test_wifi_v060_command_contracts():
    assert validate_command_payload(
        "wifi.set_radio",
        {
            "radio": "radio0",
            "enabled": True,
            "channel": "36",
            "country": "ru",
            "htmode": "he80",
            "txpower": 20,
        },
    ) == {
        "radio": "radio0",
        "enabled": True,
        "channel": "36",
        "country": "RU",
        "htmode": "HE80",
        "txpower": 20,
    }
    added = validate_command_payload(
        "wifi.add_ssid",
        {
            "radio": "radio0",
            "ssid": "Guest",
            "network": "guest",
            "encryption": "sae",
            "key": "correct-horse",
            "hidden": False,
            "isolate": True,
        },
    )
    assert added["isolate"] is True
    assert validate_command_payload(
        "wifi.set_schedule",
        {
            "radio": "radio0",
            "enabled": True,
            "weekdays": ["mon", "fri"],
            "start": "07:00",
            "stop": "23:00",
        },
    )["weekdays"] == ["mon", "fri"]


def test_wifi_schedule_rejects_invalid_window():
    with pytest.raises(HTTPException):
        validate_command_payload(
            "wifi.set_schedule",
            {
                "radio": "radio0",
                "enabled": True,
                "weekdays": ["mon"],
                "start": "07:00",
                "stop": "07:00",
            },
        )


def test_wifi_access_profile_contract_normalizes_limits_and_schedule():
    payload = validate_command_payload(
        "wifi.set_access_profile",
        {
            "iface": "guest",
            "enabled": True,
            "profile_id": "f3dcf7c2-5641-4f62-82d1-8a5af2c9cdb2",
            "profile_name": "Guests",
            "blocked": False,
            "schedule": {
                "enabled": True,
                "weekdays": ["sat", "sun"],
                "start": "09:00",
                "stop": "23:00",
            },
            "qos": {"download_kbps": 20000, "upload_kbps": 5000},
        },
    )
    assert payload["iface"] == "guest"
    assert payload["schedule"]["weekdays"] == ["sat", "sun"]
    assert payload["qos"] == {"download_kbps": 20000, "upload_kbps": 5000}


def test_wifi_access_profile_rejects_invalid_limit():
    with pytest.raises(HTTPException):
        validate_command_payload(
            "wifi.set_access_profile",
            {
                "iface": "guest",
                "enabled": True,
                "profile_id": "f3dcf7c2-5641-4f62-82d1-8a5af2c9cdb2",
                "profile_name": "Guests",
                "qos": {"download_kbps": -1},
            },
        )


def test_web_form_builds_wifi_schedule_array():
    payload = build_command_payload_from_web_form(
        "wifi.set_schedule",
        radio="radio1",
        enabled="true",
        weekdays=["sat", "sun"],
        start="09:00",
        stop="22:30",
    )
    assert payload == {
        "radio": "radio1",
        "enabled": True,
        "weekdays": ["sat", "sun"],
        "start": "09:00",
        "stop": "22:30",
    }


def test_wifi_station_telemetry_is_flattened():
    summary = normalize_wifi_summary(
        {
            "wifi": {
                "available": True,
                "radios": [],
                "stations": [
                    {
                        "interface": "wlan0",
                        "ssid": "HomeNET",
                        "band": "5g",
                        "clients": {
                            "AA:BB:CC:DD:EE:FF": {
                                "signal": -48,
                                "noise": -94,
                                "tx_rate": "866 Mbit/s",
                            }
                        },
                    }
                ],
            }
        }
    )
    assert summary["station_count"] == 1
    assert summary["stations"][0]["mac"] == "aa:bb:cc:dd:ee:ff"
    assert summary["stations"][0]["signal"] == -48
    assert summary["stations"][0]["ssid"] == "HomeNET"
    assert summary["stations"][0]["band"] == "5g"


def test_wifi_access_profile_observed_state_is_preserved():
    summary = normalize_wifi_summary(
        {
            "wifi": {
                "available": True,
                "radios": [
                    {
                        "id": "radio0",
                        "interfaces": [
                            {
                                "id": "guest",
                                "mode": "ap",
                                "network": "guest",
                                "ssid": "Guests",
                                "access_profile": {
                                    "configured": True,
                                    "profile_id": "profile-1",
                                    "profile_name": "Guests",
                                    "effective_enabled": True,
                                    "qos": {
                                        "download_kbps": 20000,
                                        "upload_kbps": 5000,
                                        "download_active": True,
                                        "upload_active": True,
                                    },
                                },
                            }
                        ],
                    }
                ],
            }
        }
    )
    observed = summary["networks"][0]["access_profile"]
    assert observed["profile_id"] == "profile-1"
    assert observed["qos"]["download_active"] is True


def test_wifi_station_airtime_is_split_and_raw_object_is_not_exposed():
    summary = normalize_wifi_summary(
        {
            "wifi": {
                "available": True,
                "stations": [
                    {
                        "interface": "phy1-ap0",
                        "clients": {
                            "02:A3:B0:9B:7E:0A": {
                                "signal": -63,
                                "airtime": {"rx": 707019, "tx": 609153},
                            }
                        },
                    }
                ],
            }
        }
    )
    station = summary["stations"][0]
    assert station["airtime_rx_us"] == 707019
    assert station["airtime_tx_us"] == 609153
    assert summary["has_station_airtime"] is True
    assert summary["has_station_rates"] is False


def test_wifi_station_numeric_rates_are_preserved_when_driver_reports_them():
    summary = normalize_wifi_summary(
        {
            "wifi": {
                "stations": [
                    {
                        "clients": {
                            "00:11:22:33:44:55": {
                                "rx": {"rate": 650000},
                                "tx": {"bitrate": 866700},
                            }
                        }
                    }
                ]
            }
        }
    )
    assert summary["stations"][0]["rx_bitrate"] == 650000
    assert summary["stations"][0]["tx_bitrate"] == 866700
    assert summary["has_station_rates"] is True


def test_wifi_radio_survey_is_normalized_without_inventing_metrics():
    summary = normalize_wifi_summary(
        {
            "wifi": {
                "radios": [
                    {
                        "id": "radio1",
                        "band": "5g",
                        "survey": {
                            "state": "observed",
                            "interface": "phy1-ap0",
                            "frequency_mhz": 5180,
                            "noise_dbm": -95,
                            "active_ms": 1000,
                            "busy_ms": 421,
                            "utilization_percent": 42,
                        },
                    },
                    {"id": "radio2", "band": "6g"},
                ]
            }
        }
    )

    assert summary["radios"][0]["survey"] == {
        "state": "observed",
        "reason": "",
        "interface": "phy1-ap0",
        "frequency_mhz": 5180,
        "noise_dbm": -95,
        "active_ms": 1000,
        "busy_ms": 421,
        "rx_ms": None,
        "tx_ms": None,
        "utilization_percent": 42,
    }
    assert summary["radios"][1]["survey"]["state"] == "unsupported"
    assert summary["radios"][1]["survey"]["utilization_percent"] is None


def test_wifi_contract_preserves_runtime_channels_and_network_roles():
    summary = normalize_wifi_summary(
        {
            "wifi": {
                "available": True,
                "state": "observed",
                "radios": [
                    {
                        "id": "radio1",
                        "band": "5g",
                        "configured_enabled": True,
                        "runtime": {
                            "state": "up",
                            "up": True,
                            "pending": False,
                            "ifname": "phy1-ap0",
                        },
                        "supported_channels": ["auto", "36", "40"],
                        "interfaces": [
                            {
                                "id": "default_radio1",
                                "ssid": "HomeNET",
                                "mode": "ap",
                                "network": "lan",
                                "enabled": True,
                            },
                            {
                                "id": "guest_radio1",
                                "ssid": "Guest",
                                "mode": "ap",
                                "network": "guest",
                                "isolate": True,
                                "enabled": True,
                            },
                        ],
                    }
                ],
                "stations": [],
            }
        }
    )
    radio = summary["radios"][0]
    assert radio["runtime"]["ifname"] == "phy1-ap0"
    assert radio["supported_channels"] == ["auto", "36", "40"]
    assert [item["role"] for item in summary["networks"]] == [
        "primary",
        "guest",
    ]


def test_wifi_schedule_keeps_configured_runtime_and_effective_state_separate():
    summary = normalize_wifi_summary(
        {
            "wifi": {
                "available": True,
                "radios": [
                    {
                        "id": "radio0",
                        "configured_enabled": True,
                        "runtime": {"state": "down", "up": False},
                        "schedule": {
                            "enabled": True,
                            "weekdays": ["mon", "tue"],
                            "start": "07:00",
                            "stop": "23:00",
                            "active_now": False,
                            "base_enabled": True,
                            "effective_enabled": False,
                        },
                    },
                    {
                        "id": "radio1",
                        "configured_enabled": True,
                        "runtime": {"state": "up", "up": True},
                        "schedule": {
                            "enabled": False,
                            "weekdays": [],
                            "start": "",
                            "stop": "",
                        },
                    },
                ],
                "stations": [],
            }
        }
    )
    first, second = summary["radios"]
    assert first["configured_enabled"] is True
    assert first["runtime"]["up"] is False
    assert first["schedule"] == {
        "enabled": True,
        "weekdays": ["mon", "tue"],
        "start": "07:00",
        "stop": "23:00",
        "active_now": False,
        "base_enabled": True,
        "effective_enabled": False,
    }
    assert second["schedule"]["enabled"] is False
    assert second["schedule"]["weekdays"] == []
    assert second["schedule"]["effective_enabled"] is True


def test_existing_mesh_can_keep_its_password():
    payload = validate_command_payload(
        "wifi.set_mesh",
        {
            "radio": "radio1",
            "enabled": True,
            "mesh_id": "WrtMesh",
            "network": "lan",
            "encryption": "sae",
            "key": "",
        },
    )
    assert payload == {
        "radio": "radio1",
        "enabled": True,
        "mesh_id": "WrtMesh",
        "network": "lan",
        "encryption": "sae",
    }


def test_wifi_web_forms_are_populated_from_selected_radio():
    template = (
        Path(__file__).parents[1] / "app" / "templates" / "partials" / "wifi.html"
    ).read_text(encoding="utf-8")
    script = (
        Path(__file__).parents[1] / "app" / "static" / "wifi-settings.js"
    ).read_text(encoding="utf-8")
    assert 'data-wifi-schedule-field="enabled"' in template
    assert 'value="true" selected' not in template
    assert "radio?.schedule || {}" in script
    assert "scheduleRadio.addEventListener('change', renderSchedule)" in script
    assert "bindNetworkForm('guest'" in script
    assert "bindNetworkForm('mesh'" in script


def test_wifi_contract_marks_router_without_radio_as_unsupported():
    summary = normalize_wifi_summary(
        {
            "wifi": {
                "available": False,
                "state": "unsupported",
                "reason": "no_wifi_radio",
                "radios": [],
                "stations": [],
            }
        }
    )
    assert summary["state"] == "unsupported"
    assert summary["reason"] == "no_wifi_radio"
    assert summary["radios"] == []
    assert summary["networks"] == []


def test_wifi_station_count_does_not_duplicate_same_ssid_across_bands():
    summary = normalize_wifi_summary(
        {
            "wifi": {
                "available": True,
                "radios": [
                    {
                        "id": "radio0",
                        "band": "2g",
                        "interfaces": [{"id": "ap2", "mode": "ap", "ssid": "Home"}],
                    },
                    {
                        "id": "radio1",
                        "band": "5g",
                        "interfaces": [{"id": "ap5", "mode": "ap", "ssid": "Home"}],
                    },
                ],
                "stations": [
                    {
                        "interface": "phy1-ap0",
                        "ssid": "Home",
                        "band": "5g",
                        "clients": {"00:11:22:33:44:55": {"signal": -48}},
                    }
                ],
            }
        }
    )

    assert [item["station_count"] for item in summary["networks"]] == [0, 1]
