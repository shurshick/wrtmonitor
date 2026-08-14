from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import DeviceHardwareIdentity, HardwareSensorSample
from .hardware_profiles import CATALOG_VERSION


def _temperature_status(
    current: int | None, warning: int | None, critical: int | None
) -> str:
    if current is None:
        return "stale"
    if critical is not None and current >= critical:
        return "critical"
    if warning is not None and current >= warning:
        return "warning"
    if warning is not None or critical is not None:
        return "normal"
    return "unknown"


def hardware_summary(
    db: Session, device_id: UUID, payload: dict[str, Any] | None
) -> dict[str, Any]:
    from .hardware_catalog import _resolved_hardware

    telemetry = payload or {}
    raw_hardware = telemetry.get("hardware") or {}
    raw_cpu = telemetry.get("cpu") or {}
    raw_thermal = (
        telemetry.get("thermal") if isinstance(telemetry.get("thermal"), dict) else {}
    )
    raw_sensors = raw_thermal.get("sensors") or []
    identity = db.get(DeviceHardwareIdentity, device_id)
    resolved = (
        dict(identity.resolved)
        if identity
        else _resolved_hardware(raw_hardware, raw_cpu, None)
    )
    if raw_cpu:
        resolved["cpu"] = _resolved_hardware(raw_hardware, raw_cpu, None)["cpu"]
    current_sensors = {
        str(item.get("id") or item.get("type")): item
        for item in raw_sensors
        if isinstance(item, dict)
    }
    stats = db.execute(
        select(
            HardwareSensorSample.sensor_key,
            func.min(HardwareSensorSample.milli_celsius),
            func.max(HardwareSensorSample.milli_celsius),
            func.count(HardwareSensorSample.id),
            func.max(HardwareSensorSample.label),
            func.max(HardwareSensorSample.role),
            func.max(HardwareSensorSample.warning_milli_celsius),
            func.max(HardwareSensorSample.critical_milli_celsius),
            func.max(HardwareSensorSample.subsystem),
        )
        .where(HardwareSensorSample.device_id == device_id)
        .group_by(HardwareSensorSample.sensor_key)
    ).all()
    grouped: dict[str, dict[str, Any]] = {}
    for (
        key,
        minimum,
        maximum,
        count,
        label,
        role,
        warning,
        critical,
        subsystem,
    ) in stats:
        current_item = current_sensors.get(key, {})
        group_key = role or key
        item = grouped.setdefault(
            group_key,
            {
                "key": group_key,
                "label": label,
                "role": role,
                "current_milli_celsius": None,
                "min_milli_celsius": minimum,
                "max_milli_celsius": maximum,
                "sample_count": 0,
                "source_count": 0,
                "warning_milli_celsius": warning,
                "critical_milli_celsius": critical,
                "state": "stale",
                "_preferred": -1,
            },
        )
        item["min_milli_celsius"] = min(item["min_milli_celsius"], minimum)
        item["max_milli_celsius"] = max(item["max_milli_celsius"], maximum)
        item["sample_count"] += count
        item["source_count"] += 1
        item["warning_milli_celsius"] = item["warning_milli_celsius"] or warning
        item["critical_milli_celsius"] = item["critical_milli_celsius"] or critical
        preferred = (
            2
            if current_item.get("subsystem") == "thermal" or subsystem == "thermal"
            else 1
        )
        if current_item and preferred > item["_preferred"]:
            item["current_milli_celsius"] = current_item.get("milli_celsius")
            item["warning_milli_celsius"] = (
                current_item.get("warning_milli_celsius")
                or item["warning_milli_celsius"]
            )
            item["critical_milli_celsius"] = (
                current_item.get("critical_milli_celsius")
                or item["critical_milli_celsius"]
            )
            item["state"] = "observed"
            item["_preferred"] = preferred
    sensors = []
    for item in grouped.values():
        item.pop("_preferred", None)
        item["thermal_status"] = _temperature_status(
            item["current_milli_celsius"],
            item["warning_milli_celsius"],
            item["critical_milli_celsius"],
        )
        limit = item["critical_milli_celsius"] or item["warning_milli_celsius"]
        item["headroom_milli_celsius"] = (
            limit - item["current_milli_celsius"]
            if limit is not None and item["current_milli_celsius"] is not None
            else None
        )
        sensors.append(item)
    rank = {"critical": 4, "warning": 3, "stale": 2, "unknown": 1, "normal": 0}
    thermal_health = max(
        (item["thermal_status"] for item in sensors),
        key=lambda value: rank[value],
        default="unsupported",
    )
    resolved["sensors"] = sorted(
        sensors, key=lambda item: (item["role"] is None, item["label"])
    )
    resolved["raw_sensor_count"] = len(raw_sensors)
    resolved["thermal_health"] = thermal_health
    resolved["throttling"] = raw_thermal.get("throttling") or {
        "state": "unsupported",
        "active": None,
    }
    resolved["match"] = {
        "method": identity.match_method if identity else None,
        "confidence": identity.match_confidence if identity else 0,
    }
    return resolved


def hardware_report(
    db: Session,
    device_id: UUID,
    payload: dict[str, Any] | None,
    device: Any | None = None,
) -> dict[str, Any]:
    telemetry = payload or {}
    summary = hardware_summary(db, device_id, telemetry)
    raw_thermal = (
        telemetry.get("thermal") if isinstance(telemetry.get("thermal"), dict) else {}
    )
    sensors = (
        raw_thermal.get("sensors")
        if isinstance(raw_thermal.get("sensors"), list)
        else []
    )
    return {
        "schema": "wrtmonitor.hardware-report.v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "catalog_version": CATALOG_VERSION,
        "device": {
            "id": str(device_id),
            "name": getattr(device, "name", None),
            "hostname": getattr(device, "hostname", None),
            "model": getattr(device, "model", None),
            "firmware": getattr(device, "firmware", None),
        },
        "identity": summary,
        "observed": {
            "hardware": telemetry.get("hardware") or {},
            "cpu": telemetry.get("cpu") or {},
            "thermal": {
                "state": raw_thermal.get("state", "unsupported"),
                "available": bool(raw_thermal.get("available")),
                "sensors": sensors,
                "throttling": raw_thermal.get("throttling")
                or {
                    "state": "unsupported",
                    "active": None,
                },
            },
        },
    }
