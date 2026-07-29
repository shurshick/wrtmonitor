from __future__ import annotations

from typing import Any


def normalize_maintenance_summary(payload: dict[str, Any]) -> dict[str, Any]:
    maintenance = payload.get("maintenance") or {}
    if not isinstance(maintenance, dict):
        maintenance = {}
    packages = maintenance.get("packages") or {}
    if not isinstance(packages, dict):
        packages = {}
    modules = payload.get("modules") or {}
    if not isinstance(modules, dict):
        modules = {}
    return {
        "package_manager": str(packages.get("manager") or ""),
        "installed_packages": int(
            packages.get("installed", maintenance.get("installed_packages")) or 0
        ),
        "upgradable_packages": int(
            packages.get("upgradable", maintenance.get("upgradable_packages")) or 0
        ),
        "installed_items": [
            item
            for item in packages.get("installed_items") or []
            if isinstance(item, dict)
        ],
        "upgradable_items": [
            item
            for item in packages.get("upgradable_items") or []
            if isinstance(item, dict)
        ],
        "cron_entries": int(maintenance.get("cron_entries") or 0),
        "cron_content": str(maintenance.get("cron_content") or ""),
        "services": [
            {
                "name": str(item.get("name") or ""),
                "running": bool(item.get("running")),
                "enabled": bool(item.get("enabled")),
            }
            for item in maintenance.get("services") or []
            if isinstance(item, dict) and item.get("name")
        ],
        "process_snapshot": str(maintenance.get("process_snapshot") or ""),
        "recovery_mode": bool(maintenance.get("recovery_mode", False)),
        "staged_firmware_sha256": str(maintenance.get("staged_firmware_sha256") or ""),
        "modules_state": str(modules.get("state") or "unsupported"),
        "modules": [
            {
                "id": str(item.get("id") or ""),
                "supported": bool(item.get("supported")),
                "installed": bool(item.get("installed")),
                "running": bool(item.get("running")),
                "enabled": bool(item.get("enabled")),
                "hardware_count": int(item.get("hardware_count") or 0),
                "primary_package": str(item.get("primary_package") or ""),
            }
            for item in modules.get("items") or []
            if isinstance(item, dict) and item.get("id")
        ],
        "module_hardware": modules.get("hardware") or {},
    }


__all__ = ["normalize_maintenance_summary"]
