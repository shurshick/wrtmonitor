from __future__ import annotations

from typing import Any, cast

from ..schemas.command_types import ReliabilityPolicy


READ_ONLY = "level_1_readonly"
SAFE_ACTIONS = {"level_2_safe_action", "level_2_safe_write"}

CONNECTIVITY_COMMANDS = {
    "agent.disconnect",
    "agent.rollback",
    "agent.update",
    "maintenance.backup.restore",
    "maintenance.sysupgrade.apply",
    "network.interface_restart",
    "network.restart",
    "router.reboot",
}
AGENT_STATE_COMMANDS = {
    "agent.rotate_token",
    "agent.set_auto_update",
    "agent.set_interval",
}
PACKAGE_STATE_COMMANDS = {
    "dns.install_doh",
    "dns.install_dot",
    "maintenance.package.install",
    "maintenance.package.remove",
    "maintenance.package.upgrade",
}
SERVICE_STATE_COMMANDS = {
    "maintenance.service.set",
    "system.restart_service",
}
HANDLER_RESULT_COMMANDS = {
    "maintenance.process.signal",
    "maintenance.sysupgrade.check",
}


def command_subsystem(command_type: str) -> str:
    return command_type.split(".", 1)[0]


def command_reliability(
    command_type: str,
    metadata: dict[str, Any],
) -> ReliabilityPolicy:
    """Return the executable delivery policy included in the public contract."""
    risk = str(metadata["risk_level"])
    readonly = risk == READ_ONLY
    disruptive = risk == "level_4_disruptive"
    maintenance = command_type.startswith("maintenance.")
    timeout_seconds = 900 if maintenance else 300 if disruptive else 120
    if readonly:
        timeout_seconds = 45

    if readonly:
        post_condition = "result_payload"
        rollback = "not_required"
    elif command_type in CONNECTIVITY_COMMANDS:
        post_condition = "service_or_connectivity_state"
        rollback = "not_safe_after_dispatch"
    elif command_type in AGENT_STATE_COMMANDS:
        post_condition = "agent_state"
        rollback = "agent_previous_version_or_config"
    elif command_type in PACKAGE_STATE_COMMANDS:
        post_condition = "package_state"
        rollback = "package_manager_transaction"
    elif command_type in SERVICE_STATE_COMMANDS:
        post_condition = "service_state"
        rollback = "configuration_backup"
    elif command_type in HANDLER_RESULT_COMMANDS:
        post_condition = "handler_result"
        rollback = "not_available"
    else:
        post_condition = "read_after_write_config"
        rollback = "configuration_backup"

    return cast(
        ReliabilityPolicy,
        {
            "subsystem": command_subsystem(command_type),
            "idempotency": {
                "strategy": "command_uuid_result_cache",
                "semantic": readonly or risk in SAFE_ACTIONS,
            },
            "delivery": {
                "timeout_seconds": timeout_seconds,
                "lease_seconds": min(45, timeout_seconds),
                "max_deliveries": 3 if readonly else 2,
            },
            "post_condition": post_condition,
            "verification": {
                "required": True,
                "mode": post_condition,
                "fail_closed": True,
            },
            "rollback": rollback,
        },
    )


def apply_reliability_contract(
    registry: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    for command_type, metadata in registry.items():
        metadata["reliability"] = command_reliability(command_type, metadata)
    return registry
