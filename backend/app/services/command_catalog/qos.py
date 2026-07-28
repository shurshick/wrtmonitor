from typing import Any


COMMANDS: dict[str, dict[str, Any]] = {
    "qos.set_sqm": {
        "risk_level": "level_3_reversible_config",
        "capability": "qos.sqm",
        "requires_confirmation": True,
        "secret_fields": [],
    }
}
