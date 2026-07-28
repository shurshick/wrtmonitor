from typing import Any


COMMANDS: dict[str, dict[str, Any]] = {
    "client.set_blocked": {
        "risk_level": "level_3_reversible_config",
        "capability": "clients.block",
        "requires_confirmation": True,
        "secret_fields": [],
    },
    "client.set_policy": {
        "risk_level": "level_3_reversible_config",
        "capability": "clients.policy",
        "requires_confirmation": True,
        "secret_fields": [],
    },
}
