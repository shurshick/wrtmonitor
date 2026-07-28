from typing import Any


COMMANDS: dict[str, dict[str, Any]] = {
    "vpn.wireguard.set_interface": {
        "risk_level": "level_4_disruptive",
        "capability": "vpn.wireguard.configure",
        "requires_confirmation": True,
        "secret_fields": ["private_key"],
    },
    "vpn.wireguard.set_peer": {
        "risk_level": "level_3_reversible_config",
        "capability": "vpn.wireguard.configure",
        "requires_confirmation": True,
        "secret_fields": ["preshared_key"],
    },
    "vpn.wireguard.delete_interface": {
        "risk_level": "level_4_disruptive",
        "capability": "vpn.wireguard.configure",
        "requires_confirmation": True,
        "secret_fields": [],
    },
    "vpn.wireguard.delete_peer": {
        "risk_level": "level_3_reversible_config",
        "capability": "vpn.wireguard.configure",
        "requires_confirmation": True,
        "secret_fields": [],
    },
    "vpn.wireguard.export_peer": {
        "risk_level": "level_1_readonly",
        "capability": "vpn.wireguard.read",
        "requires_confirmation": False,
        "secret_fields": [],
    },
    "vpn.openvpn.set_client": {
        "risk_level": "level_4_disruptive",
        "capability": "vpn.openvpn.configure",
        "requires_confirmation": True,
        "secret_fields": ["config"],
    },
    "vpn.openvpn.delete_client": {
        "risk_level": "level_3_reversible_config",
        "capability": "vpn.openvpn.configure",
        "requires_confirmation": True,
        "secret_fields": [],
    },
    "vpn.openvpn.set_enabled": {
        "risk_level": "level_3_reversible_config",
        "capability": "vpn.openvpn.configure",
        "requires_confirmation": True,
        "secret_fields": [],
    },
    "vpn.openvpn.export_client": {
        "risk_level": "level_1_readonly",
        "capability": "vpn.openvpn.read",
        "requires_confirmation": False,
        "secret_fields": [],
    },
    "vpn.policy.set": {
        "risk_level": "level_4_disruptive",
        "capability": "vpn.policy.configure",
        "requires_confirmation": True,
        "secret_fields": [],
    },
    "vpn.policy.delete": {
        "risk_level": "level_3_reversible_config",
        "capability": "vpn.policy.configure",
        "requires_confirmation": True,
        "secret_fields": [],
    },
}
