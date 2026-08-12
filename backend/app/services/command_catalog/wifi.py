from typing import Any


COMMANDS: dict[str, dict[str, Any]] = {
    "wifi.status": {
        "risk_level": "level_1_readonly",
        "capability": "wifi.read",
        "requires_confirmation": False,
        "secret_fields": [],
    },
    "wifi.get_qr": {
        "risk_level": "level_1_readonly",
        "capability": "wifi.qr",
        "requires_confirmation": False,
        "secret_fields": ["wifi_uri"],
    },
    "wifi.set_enabled": {
        "risk_level": "level_3_reversible_config",
        "capability": "wifi.enable",
        "requires_confirmation": True,
        "secret_fields": [],
    },
    "wifi.set_ssid": {
        "risk_level": "level_3_reversible_config",
        "capability": "wifi.set_ssid",
        "requires_confirmation": True,
        "secret_fields": [],
    },
    "wifi.set_password": {
        "risk_level": "level_3_reversible_config",
        "capability": "wifi.set_password",
        "requires_confirmation": True,
        "secret_fields": ["password", "wifi_password", "key"],
    },
    "wifi.set_channel": {
        "risk_level": "level_3_reversible_config",
        "capability": "wifi.set_channel",
        "requires_confirmation": True,
        "secret_fields": [],
    },
    "wifi.set_country": {
        "risk_level": "level_3_reversible_config",
        "capability": "wifi.set_country",
        "requires_confirmation": True,
        "secret_fields": [],
    },
    "wifi.set_radio": {
        "risk_level": "level_3_reversible_config",
        "capability": "wifi.radio.configure",
        "requires_confirmation": True,
        "secret_fields": [],
    },
    "wifi.add_ssid": {
        "risk_level": "level_3_reversible_config",
        "capability": "wifi.manage_ssid",
        "requires_confirmation": True,
        "secret_fields": ["password", "key"],
    },
    "wifi.update_ssid": {
        "risk_level": "level_3_reversible_config",
        "capability": "wifi.manage_ssid",
        "requires_confirmation": True,
        "secret_fields": ["password", "key"],
    },
    "wifi.delete_ssid": {
        "risk_level": "level_3_reversible_config",
        "capability": "wifi.manage_ssid",
        "requires_confirmation": True,
        "secret_fields": [],
    },
    "wifi.set_schedule": {
        "risk_level": "level_3_reversible_config",
        "capability": "wifi.schedule",
        "requires_confirmation": True,
        "secret_fields": [],
    },
    "wifi.set_mesh": {
        "risk_level": "level_4_disruptive",
        "capability": "wifi.mesh",
        "requires_confirmation": True,
        "secret_fields": ["password", "key"],
    },
    "wifi.set_guest": {
        "risk_level": "level_4_disruptive",
        "capability": "wifi.guest",
        "requires_confirmation": True,
        "secret_fields": ["password", "key"],
    },
}
