from typing import Any


COMMANDS: dict[str, dict[str, Any]] = {
    "system.set_hostname": {
        "risk_level": "level_3_reversible_config",
        "capability": "system.set_hostname",
        "requires_confirmation": True,
        "secret_fields": [],
    },
    "system.restart_service": {
        "risk_level": "level_3_reversible_config",
        "capability": "system.restart_service",
        "requires_confirmation": True,
        "secret_fields": [],
    },
    "system.set_timezone": {
        "risk_level": "level_3_reversible_config",
        "capability": "system.set_timezone",
        "requires_confirmation": True,
        "secret_fields": [],
    },
    "system.set_ntp": {
        "risk_level": "level_3_reversible_config",
        "capability": "system.set_ntp",
        "requires_confirmation": True,
        "secret_fields": [],
    },
}
