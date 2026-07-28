from typing import Any


COMMANDS: dict[str, dict[str, Any]] = {
    "firewall.set_port_forward": {
        "risk_level": "level_4_disruptive",
        "capability": "firewall.port_forward",
        "requires_confirmation": True,
        "secret_fields": [],
    },
    "firewall.delete_port_forward": {
        "risk_level": "level_4_disruptive",
        "capability": "firewall.port_forward",
        "requires_confirmation": True,
        "secret_fields": [],
    },
    "firewall.set_zone": {
        "risk_level": "level_4_disruptive",
        "capability": "firewall.zones.configure",
        "requires_confirmation": True,
        "secret_fields": [],
    },
    "firewall.delete_zone": {
        "risk_level": "level_4_disruptive",
        "capability": "firewall.zones.configure",
        "requires_confirmation": True,
        "secret_fields": [],
    },
    "firewall.set_forwarding": {
        "risk_level": "level_4_disruptive",
        "capability": "firewall.zones.configure",
        "requires_confirmation": True,
        "secret_fields": [],
    },
    "firewall.delete_forwarding": {
        "risk_level": "level_4_disruptive",
        "capability": "firewall.zones.configure",
        "requires_confirmation": True,
        "secret_fields": [],
    },
    "firewall.set_rule": {
        "risk_level": "level_4_disruptive",
        "capability": "firewall.rules.configure",
        "requires_confirmation": True,
        "secret_fields": [],
    },
    "firewall.delete_rule": {
        "risk_level": "level_4_disruptive",
        "capability": "firewall.rules.configure",
        "requires_confirmation": True,
        "secret_fields": [],
    },
    "firewall.set_redirect": {
        "risk_level": "level_4_disruptive",
        "capability": "firewall.port_forward",
        "requires_confirmation": True,
        "secret_fields": [],
    },
    "firewall.delete_redirect": {
        "risk_level": "level_4_disruptive",
        "capability": "firewall.port_forward",
        "requires_confirmation": True,
        "secret_fields": [],
    },
}
