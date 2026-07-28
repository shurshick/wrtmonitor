from typing import Any


COMMANDS: dict[str, dict[str, Any]] = {
    "maintenance.packages.refresh": {
        "risk_level": "level_1_readonly",
        "capability": "maintenance.packages.read",
        "requires_confirmation": False,
        "secret_fields": [],
    },
    "maintenance.package.install": {
        "risk_level": "level_3_reversible_config",
        "capability": "maintenance.packages.write",
        "requires_confirmation": True,
        "secret_fields": [],
    },
    "maintenance.package.remove": {
        "risk_level": "level_3_reversible_config",
        "capability": "maintenance.packages.write",
        "requires_confirmation": True,
        "secret_fields": [],
    },
    "maintenance.backup.create": {
        "risk_level": "level_1_readonly",
        "capability": "maintenance.backup",
        "requires_confirmation": False,
        "secret_fields": [],
    },
    "maintenance.backup.restore": {
        "risk_level": "level_4_disruptive",
        "capability": "maintenance.backup",
        "requires_confirmation": True,
        "secret_fields": ["archive_base64"],
    },
    "maintenance.sysupgrade.check": {
        "risk_level": "level_2_safe_action",
        "capability": "maintenance.sysupgrade.check",
        "requires_confirmation": True,
        "secret_fields": [],
    },
    "maintenance.sysupgrade.apply": {
        "risk_level": "level_4_disruptive",
        "capability": "maintenance.sysupgrade.apply",
        "requires_confirmation": True,
        "secret_fields": [],
    },
    "maintenance.logs.read": {
        "risk_level": "level_1_readonly",
        "capability": "maintenance.logs",
        "requires_confirmation": False,
        "secret_fields": [],
    },
    "maintenance.process.signal": {
        "risk_level": "level_3_reversible_config",
        "capability": "maintenance.processes",
        "requires_confirmation": True,
        "secret_fields": [],
    },
    "maintenance.cron.set": {
        "risk_level": "level_3_reversible_config",
        "capability": "maintenance.cron",
        "requires_confirmation": True,
        "secret_fields": [],
    },
    "maintenance.diagnostics.bundle": {
        "risk_level": "level_1_readonly",
        "capability": "maintenance.diagnostics.bundle",
        "requires_confirmation": False,
        "secret_fields": [],
    },
    "maintenance.recovery.enable": {
        "risk_level": "level_3_reversible_config",
        "capability": "maintenance.recovery",
        "requires_confirmation": True,
        "secret_fields": [],
    },
    "maintenance.recovery.disable": {
        "risk_level": "level_2_safe_action",
        "capability": "maintenance.recovery",
        "requires_confirmation": True,
        "secret_fields": [],
    },
}
