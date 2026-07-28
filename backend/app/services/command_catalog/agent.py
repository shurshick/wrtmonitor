from typing import Any


COMMANDS: dict[str, dict[str, Any]] = {
    "agent.disconnect": {
        "risk_level": "level_3_reversible_config",
        "capability": "agent.disable",
        "requires_confirmation": True,
        "secret_fields": [],
    },
    "agent.update": {
        "risk_level": "level_2_safe_action",
        "capability": "agent.update",
        "requires_confirmation": True,
        "secret_fields": [],
    },
    "agent.rollback": {
        "risk_level": "level_2_safe_action",
        "capability": "agent.rollback",
        "requires_confirmation": True,
        "secret_fields": [],
    },
    "agent.set_auto_update": {
        "risk_level": "level_2_safe_action",
        "capability": "agent.update",
        "requires_confirmation": True,
        "secret_fields": [],
    },
    "agent.set_interval": {
        "risk_level": "level_2_safe_action",
        "capability": "agent.set_interval",
        "requires_confirmation": True,
        "secret_fields": [],
    },
    "agent.rotate_token": {
        "risk_level": "level_2_safe_action",
        "capability": "agent.rotate_token",
        "requires_confirmation": True,
        "secret_fields": [],
    },
}
