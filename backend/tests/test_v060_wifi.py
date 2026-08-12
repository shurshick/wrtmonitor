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
