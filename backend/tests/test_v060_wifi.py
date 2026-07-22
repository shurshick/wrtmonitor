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
            "channel": "36",
            "country": "ru",
            "htmode": "he80",
            "txpower": 20,
        },
    ) == {
        "radio": "radio0",
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
