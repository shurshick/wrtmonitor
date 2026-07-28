from __future__ import annotations

from typing import Any


READ_ONLY = "level_1_readonly"
SAFE_ACTIONS = {"level_2_safe_action", "level_2_safe_write"}


def command_subsystem(command_type: str) -> str:
    return command_type.split(".", 1)[0]


def command_reliability(command_type: str, metadata: dict[str, Any]) -> dict[str, Any]:
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
    elif command_type in {
        "router.reboot",
        "network.restart",
        "network.interface_restart",
        "system.service_restart",
    }:
        post_condition = "service_or_connectivity_state"
        rollback = "not_safe_after_dispatch"
    elif command_type.startswith("agent."):
        post_condition = "agent_state"
        rollback = "agent_previous_version_or_config"
    else:
        post_condition = "read_after_write_telemetry"
        rollback = "configuration_backup"

    return {
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
        "rollback": rollback,
    }


def apply_reliability_contract(
    registry: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    for command_type, metadata in registry.items():
        metadata["reliability"] = command_reliability(command_type, metadata)
    return registry
