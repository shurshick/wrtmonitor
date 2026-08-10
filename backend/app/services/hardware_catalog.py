from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from ..models import (
    DeviceHardwareIdentity,
    HardwareProfile,
    HardwareSensorSample,
)


CATALOG_VERSION = 1
NETIS_NX31_PROFILE_ID = UUID("7d92827e-2699-4ec1-814f-59a4894a0131")
BUILTIN_PROFILES = (
    {
        "id": NETIS_NX31_PROFILE_ID,
        "profile_key": "netis-nx31",
        "vendor": "Netis",
        "model": "NX31",
        "board_names": ["netis,nx31", "netis_nx31"],
        "compatibles": ["netis,nx31"],
        "target": "mediatek/filogic",
        "soc_vendor": "MediaTek",
        "soc_model": "MT7981B",
        "cpu_vendor": "Arm",
        "cpu_model": "Cortex-A53",
        "cpu_architecture": "aarch64",
        "cpu_cores": 2,
        "cpu_max_mhz": 1300,
        "sensor_roles": {
            "mt7981-thermal": {"role": "soc", "label": "SoC MediaTek MT7981B"},
            "mtk_thermal": {"role": "soc", "label": "SoC MediaTek MT7981B"},
        },
        "source_url": "https://openwrt.org/toh/hwdata/netis/netis_nx31",
    },
)


def _as_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    return []


def sync_builtin_hardware_catalog(db: Session, now: datetime | None = None) -> None:
    timestamp = now or datetime.now(UTC)
    for item in BUILTIN_PROFILES:
        profile = db.get(HardwareProfile, item["id"])
        changed = profile is None
        if profile is None:
            profile = HardwareProfile(
                id=item["id"],
                profile_key=item["profile_key"],
                vendor=item["vendor"],
                model=item["model"],
                created_at=timestamp,
                updated_at=timestamp,
            )
            db.add(profile)
        for key, value in item.items():
            if key not in {"id", "created_at"}:
                if getattr(profile, key) != value:
                    setattr(profile, key, value)
                    changed = True
        if profile.catalog_version != CATALOG_VERSION:
            profile.catalog_version = CATALOG_VERSION
            changed = True
        if changed:
            profile.updated_at = timestamp
    db.flush()


def _match_profile(
    db: Session, hardware: dict[str, Any]
) -> tuple[HardwareProfile | None, str | None, int]:
    compatibles = {item.lower() for item in _as_list(hardware.get("compatible"))}
    board_name = str(hardware.get("board_name") or "").strip().lower()
    model = str(hardware.get("model") or "").strip().lower()
    best: tuple[HardwareProfile | None, str | None, int] = (None, None, 0)
    for profile in db.scalars(select(HardwareProfile)).all():
        profile_compatibles = {str(item).lower() for item in profile.compatibles}
        profile_boards = {str(item).lower() for item in profile.board_names}
        score, method = 0, None
        if compatibles & profile_compatibles:
            score, method = 100, "device-tree-compatible"
        elif board_name and board_name in profile_boards:
            score, method = 95, "board-name"
        elif model and f"{profile.vendor} {profile.model}".lower() in model:
            score, method = 80, "model"
        if score > best[2]:
            best = (profile, method, score)
    return best


def _resolved_hardware(
    hardware: dict[str, Any], cpu: dict[str, Any], profile: HardwareProfile | None
) -> dict[str, Any]:
    resolved = {
        "state": "observed" if hardware or cpu else "unsupported",
        "model": hardware.get("model"),
        "board_name": hardware.get("board_name"),
        "compatible": _as_list(hardware.get("compatible")),
        "target": hardware.get("target"),
        "package_arch": hardware.get("package_arch"),
        "architecture": cpu.get("architecture") or hardware.get("architecture"),
        "cpu": {
            "observed_model": cpu.get("model"),
            "compatible": cpu.get("compatible"),
            "cores": cpu.get("cores"),
            "current_khz": cpu.get("current_khz"),
            "max_khz": cpu.get("max_khz"),
            "frequencies": cpu.get("frequencies") or [],
        },
        "catalog": None,
    }
    if profile:
        resolved["catalog"] = {
            "profile_key": profile.profile_key,
            "vendor": profile.vendor,
            "model": profile.model,
            "soc_vendor": profile.soc_vendor,
            "soc_model": profile.soc_model,
            "cpu_vendor": profile.cpu_vendor,
            "cpu_model": profile.cpu_model,
            "cpu_architecture": profile.cpu_architecture,
            "cpu_cores": profile.cpu_cores,
            "cpu_max_mhz": profile.cpu_max_mhz,
            "source_url": profile.source_url,
            "catalog_version": profile.catalog_version,
        }
    return resolved


def record_hardware_observation(
    db: Session,
    device_id: UUID,
    payload: dict[str, Any],
    observed_at: datetime,
) -> dict[str, Any]:
    sync_builtin_hardware_catalog(db, observed_at)
    hardware = (
        payload.get("hardware") if isinstance(payload.get("hardware"), dict) else {}
    )
    cpu = payload.get("cpu") if isinstance(payload.get("cpu"), dict) else {}
    thermal = payload.get("thermal") if isinstance(payload.get("thermal"), dict) else {}
    profile, method, confidence = _match_profile(db, hardware)
    observed = {"hardware": hardware, "cpu": cpu}
    resolved = _resolved_hardware(hardware, cpu, profile)
    identity = db.get(DeviceHardwareIdentity, device_id)
    if identity is None:
        identity = DeviceHardwareIdentity(device_id=device_id, updated_at=observed_at)
        db.add(identity)
    identity.profile_id = profile.id if profile else None
    identity.observed = observed
    identity.resolved = resolved
    identity.match_method = method
    identity.match_confidence = confidence
    identity.updated_at = observed_at

    sensor_roles = profile.sensor_roles if profile else {}
    for sensor in thermal.get("sensors") or []:
        if not isinstance(sensor, dict):
            continue
        value = sensor.get("milli_celsius")
        if not isinstance(value, int) or not -100_000 <= value <= 250_000:
            continue
        sensor_type = str(sensor.get("type") or "unknown")
        mapping = (
            sensor_roles.get(sensor_type, {}) if isinstance(sensor_roles, dict) else {}
        )
        key = str(sensor.get("id") or sensor_type)[:160]
        latest_sample = db.scalars(
            select(HardwareSensorSample)
            .where(
                HardwareSensorSample.device_id == device_id,
                HardwareSensorSample.sensor_key == key,
            )
            .order_by(HardwareSensorSample.observed_at.desc())
            .limit(1)
        ).first()
        if latest_sample and observed_at - latest_sample.observed_at < timedelta(
            minutes=1
        ):
            continue
        db.add(
            HardwareSensorSample(
                id=uuid4(),
                device_id=device_id,
                sensor_key=key,
                role=mapping.get("role"),
                label=str(mapping.get("label") or sensor.get("label") or sensor_type)[
                    :160
                ],
                subsystem=str(sensor.get("subsystem") or "thermal")[:40],
                milli_celsius=value,
                observed_at=observed_at,
            )
        )
    cutoff = observed_at - timedelta(days=45)
    db.execute(
        delete(HardwareSensorSample).where(
            HardwareSensorSample.device_id == device_id,
            HardwareSensorSample.observed_at < cutoff,
        )
    )
    db.flush()
    return resolved


def hardware_summary(
    db: Session, device_id: UUID, payload: dict[str, Any] | None
) -> dict[str, Any]:
    telemetry = payload or {}
    raw_hardware = telemetry.get("hardware") or {}
    raw_cpu = telemetry.get("cpu") or {}
    raw_sensors = (telemetry.get("thermal") or {}).get("sensors") or []
    if not raw_hardware and not raw_sensors:
        return _resolved_hardware(raw_hardware, raw_cpu, None) | {
            "sensors": [],
            "match": {"method": None, "confidence": 0},
        }
    identity = db.get(DeviceHardwareIdentity, device_id)
    resolved = (
        dict(identity.resolved)
        if identity
        else _resolved_hardware(raw_hardware, raw_cpu, None)
    )
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
        )
        .where(HardwareSensorSample.device_id == device_id)
        .group_by(HardwareSensorSample.sensor_key)
    ).all()
    resolved["sensors"] = [
        {
            "key": key,
            "label": label,
            "role": role,
            "current_milli_celsius": current_sensors.get(key, {}).get("milli_celsius"),
            "min_milli_celsius": minimum,
            "max_milli_celsius": maximum,
            "sample_count": count,
            "state": "observed" if key in current_sensors else "stale",
        }
        for key, minimum, maximum, count, label, role in stats
    ]
    resolved["match"] = {
        "method": identity.match_method if identity else None,
        "confidence": identity.match_confidence if identity else 0,
    }
    return resolved


__all__ = [
    "CATALOG_VERSION",
    "hardware_summary",
    "record_hardware_observation",
    "sync_builtin_hardware_catalog",
]
