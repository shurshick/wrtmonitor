from typing import Any


COMMANDS: dict[str, dict[str, Any]] = {
    "dhcp.set_lease": {
        "risk_level": "level_3_reversible_config",
        "capability": "dhcp.set_lease",
        "requires_confirmation": True,
        "secret_fields": [],
    },
    "dhcp.delete_lease": {
        "risk_level": "level_3_reversible_config",
        "capability": "dhcp.delete_lease",
        "requires_confirmation": True,
        "secret_fields": [],
    },
    "dhcp.set_pool": {
        "risk_level": "level_3_reversible_config",
        "capability": "dhcp.configure",
        "requires_confirmation": True,
        "secret_fields": [],
    },
}
