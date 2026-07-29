from __future__ import annotations

from datetime import timedelta
from typing import Any

from ..models import DeviceTelemetryMetric

TELEMETRY_STALE_SECONDS = 5 * 60
TELEMETRY_WINDOWS = {
    "live": (timedelta(hours=2), 120),
    "24h": (timedelta(hours=24), 288),
    "7d": (timedelta(days=7), 336),
    "30d": (timedelta(days=30), 360),
}


def _safe_int(value: Any) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def _safe_float(value: Any) -> float:
    try:
        return round(max(0.0, float(value or 0)), 2)
    except (TypeError, ValueError):
        return 0.0


def extract_agent_status(payload: dict[str, Any]) -> dict[str, Any]:
    agent = payload.get("agent") or {}
    capabilities = extract_agent_capabilities(payload)
    return {
        "version": agent.get("version"),
        "status": agent.get("status", "running"),
        "platform": agent.get("platform", "openwrt"),
        "capabilities_version": agent.get("capabilities_version"),
        "auto_update_enabled": bool(agent.get("auto_update_enabled", False)),
        "telemetry_interval_seconds": agent.get("telemetry_interval_seconds"),
        "last_update_status": agent.get("last_update_status") or "",
        "last_update_error": agent.get("last_update_error") or "",
        "last_update_check": agent.get("last_update_check") or "",
        "last_successful_update": agent.get("last_successful_update") or "",
        "available_version": agent.get("available_version") or "",
        "rollback_available": bool(agent.get("backup_available", False)),
        "backup_available": bool(agent.get("backup_available", False)),
        "update_source": agent.get("update_source") or "",
        "capabilities": capabilities,
        "capability_details": extract_agent_capability_details(payload),
    }


def extract_agent_capabilities(payload: dict[str, Any]) -> dict[str, bool]:
    agent = payload.get("agent") or {}
    capabilities = agent.get("capabilities") or {}
    if not isinstance(capabilities, dict):
        return {}
    return {str(key): bool(value) for key, value in capabilities.items()}


def extract_agent_capability_details(
    payload: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    agent = payload.get("agent") or {}
    details = agent.get("capability_details") or {}
    if not isinstance(details, dict):
        return {}
    normalized: dict[str, dict[str, Any]] = {}
    for key, detail in details.items():
        if not isinstance(detail, dict):
            continue
        normalized[str(key)] = {
            "supported": bool(detail.get("supported", False)),
            "reason": str(detail.get("reason") or ""),
        }
    return normalized


def _average_optional(
    rows: list[DeviceTelemetryMetric], field: str, digits: int
) -> int | float | None:
    values = [value for row in rows if (value := getattr(row, field)) is not None]
    if not values:
        return None
    result = round(sum(values) / len(values), digits)
    return int(result) if digits == 0 else result


def _optional_nonnegative_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return None


def _optional_int(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _optional_percent(value: Any) -> int | None:
    parsed = _optional_nonnegative_int(value)
    return min(parsed, 100) if parsed is not None else None


def _station_rate(value: Any) -> int | float | str | None:
    if isinstance(value, dict):
        value = value.get("rate", value.get("bitrate", value.get("bitrate_kbps")))
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return value if value > 0 else None
    return str(value)


def _optional_float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _kb_to_mb(value: Any) -> int | None:
    parsed = _optional_int(value)
    return parsed // 1024 if parsed is not None else None


def _millidegrees_to_celsius(value: Any) -> float | None:
    parsed = _optional_float(value)
    return parsed / 1000 if parsed is not None else None


__all__ = [
    "TELEMETRY_STALE_SECONDS",
    "TELEMETRY_WINDOWS",
    "_safe_int",
    "_safe_float",
    "extract_agent_status",
    "extract_agent_capabilities",
    "extract_agent_capability_details",
    "_average_optional",
    "_optional_nonnegative_int",
    "_optional_int",
    "_optional_percent",
    "_station_rate",
    "_optional_float",
    "_kb_to_mb",
    "_millidegrees_to_celsius",
]
