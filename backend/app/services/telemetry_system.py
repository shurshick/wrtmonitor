from __future__ import annotations

from typing import Any


def normalize_services_summary(payload: dict[str, Any]) -> dict[str, str]:
    services = (payload.get("system") or {}).get("services") or {}
    if not isinstance(services, dict):
        return {}
    return {str(name): str(status) for name, status in services.items()}


def normalize_system_summary(payload: dict[str, Any]) -> dict[str, Any]:
    system = payload.get("system") or {}
    conntrack = system.get("conntrack") or {}
    time_config = system.get("time") or {}
    return {
        "hostname": system.get("hostname"),
        "kernel": system.get("kernel"),
        "local_time": system.get("local_time"),
        "uptime_seconds": system.get("uptime"),
        "load_1m": system.get("load"),
        "load_5m": system.get("load_5m"),
        "load_15m": system.get("load_15m"),
        "conntrack_count": conntrack.get("count"),
        "conntrack_max": conntrack.get("max"),
        "zonename": time_config.get("zonename"),
        "timezone": time_config.get("timezone"),
        "ntp_enabled": time_config.get("ntp_enabled"),
        "ntp_servers": time_config.get("ntp_servers") or [],
        "services": normalize_services_summary(payload),
    }


__all__ = ["normalize_services_summary", "normalize_system_summary"]
