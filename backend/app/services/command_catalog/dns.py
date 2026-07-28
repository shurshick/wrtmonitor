from typing import Any


COMMANDS: dict[str, dict[str, Any]] = {
    "dns.set_servers": {
        "risk_level": "level_3_reversible_config",
        "capability": "dns.configure",
        "requires_confirmation": True,
        "secret_fields": [],
    },
    "dns.install_dot": {
        "risk_level": "level_2_safe_write",
        "capability": "dns.encrypted.install",
        "requires_confirmation": True,
        "secret_fields": [],
    },
    "dns.install_doh": {
        "risk_level": "level_2_safe_write",
        "capability": "dns.encrypted.install",
        "requires_confirmation": True,
        "secret_fields": [],
    },
    "dns.set_dot": {
        "risk_level": "level_3_reversible_config",
        "capability": "dns.dot.configure",
        "requires_confirmation": True,
        "secret_fields": [],
    },
    "dns.set_doh": {
        "risk_level": "level_3_reversible_config",
        "capability": "dns.doh.configure",
        "requires_confirmation": True,
        "secret_fields": [],
    },
}
