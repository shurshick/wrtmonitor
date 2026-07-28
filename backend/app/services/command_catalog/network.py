from typing import Any


COMMANDS: dict[str, dict[str, Any]] = {
    "network.interfaces": {
        "risk_level": "level_1_readonly",
        "capability": "network.read",
        "requires_confirmation": False,
        "secret_fields": [],
    },
    "network.interface_restart": {
        "risk_level": "level_3_reversible_config",
        "capability": "network.interface_restart",
        "requires_confirmation": True,
        "secret_fields": [],
    },
    "network.restart": {
        "risk_level": "level_4_disruptive",
        "capability": "network.restart",
        "requires_confirmation": True,
        "secret_fields": [],
    },
    "network.set_wan": {
        "risk_level": "level_4_disruptive",
        "capability": "network.wan.configure",
        "requires_confirmation": True,
        "secret_fields": ["password"],
    },
    "network.set_lan": {
        "risk_level": "level_4_disruptive",
        "capability": "network.lan.configure",
        "requires_confirmation": True,
        "secret_fields": [],
    },
    "network.set_ipv6": {
        "risk_level": "level_4_disruptive",
        "capability": "network.ipv6.configure",
        "requires_confirmation": True,
        "secret_fields": [],
    },
    "network.set_segment": {
        "risk_level": "level_4_disruptive",
        "capability": "network.segments.configure",
        "requires_confirmation": True,
        "secret_fields": [],
    },
    "network.delete_segment": {
        "risk_level": "level_4_disruptive",
        "capability": "network.segments.configure",
        "requires_confirmation": True,
        "secret_fields": [],
    },
    "network.set_vlan": {
        "risk_level": "level_4_disruptive",
        "capability": "network.vlan.configure",
        "requires_confirmation": True,
        "secret_fields": [],
    },
    "network.delete_vlan": {
        "risk_level": "level_4_disruptive",
        "capability": "network.vlan.configure",
        "requires_confirmation": True,
        "secret_fields": [],
    },
    "network.set_multiwan": {
        "risk_level": "level_4_disruptive",
        "capability": "network.multiwan.configure",
        "requires_confirmation": True,
        "secret_fields": [],
    },
    "network.set_route": {
        "risk_level": "level_3_reversible_config",
        "capability": "network.routes.configure",
        "requires_confirmation": True,
        "secret_fields": [],
    },
    "network.delete_route": {
        "risk_level": "level_3_reversible_config",
        "capability": "network.routes.configure",
        "requires_confirmation": True,
        "secret_fields": [],
    },
    "network.set_ddns": {
        "risk_level": "level_3_reversible_config",
        "capability": "network.ddns.configure",
        "requires_confirmation": True,
        "secret_fields": ["password"],
    },
    "network.set_upnp": {
        "risk_level": "level_3_reversible_config",
        "capability": "firewall.upnp.configure",
        "requires_confirmation": True,
        "secret_fields": [],
    },
}
