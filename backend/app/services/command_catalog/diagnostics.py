from typing import Any


COMMANDS: dict[str, dict[str, Any]] = {
    "diagnostics.run": {
        "risk_level": "level_1_readonly",
        "capability": "diagnostics.check_server",
        "requires_confirmation": False,
        "secret_fields": [],
    }
}
