from typing import Any


COMMANDS: dict[str, dict[str, Any]] = {
    "router.reboot": {
        "risk_level": "level_3_reversible_config",
        "capability": "system.reboot",
        "requires_confirmation": True,
        "secret_fields": [],
    }
}
