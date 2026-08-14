from __future__ import annotations

from datetime import UTC, datetime, timedelta
from hashlib import sha256
from typing import Any
from uuid import UUID, uuid4, uuid5

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ..models import DeviceHardwareIdentity, HardwareProfile, HardwareSensorSample
from .hardware_profiles import (
    BUILTIN_PROFILES,
    CATALOG_VERSION,
    NETIS_NX31_PROFILE_ID,
    PROFILE_NAMESPACE,
)
from .hardware_reporting import _temperature_status as _temperature_status


def _as_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    return []


def _positive_int(value: Any) -> int | None:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


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
        values = item | {"origin": "builtin", "verified": True}
        for key, value in values.items():
            if key not in {"id", "created_at"} and getattr(profile, key) != value:
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
        elif (
            profile.origin == "builtin"
            and model
            and f"{profile.vendor} {profile.model}".lower() in model
        ):
            score, method = 80, "model"
        if score > best[2]:
            best = (profile, method, score)
    return best


def _learn_profile(
    db: Session, hardware: dict[str, Any], cpu: dict[str, Any], now: datetime
) -> HardwareProfile | None:
    board_name = str(hardware.get("board_name") or "").strip()
    compatibles = _as_list(hardware.get("compatible"))
    model = str(hardware.get("model") or "").strip()
    target = str(hardware.get("target") or "").strip() or None
    identity_parts = [
        board_name.lower(),
        *(item.lower() for item in compatibles),
        model.lower(),
        target or "",
    ]
    stable_identity = "|".join(part for part in identity_parts if part)
    if not stable_identity:
        return None
    digest = sha256(stable_identity.encode("utf-8")).hexdigest()[:20]
    profile_key = f"observed-{digest}"
    profile = db.scalar(
        select(HardwareProfile).where(HardwareProfile.profile_key == profile_key)
    )
    if profile is None:
        profile = HardwareProfile(
            id=uuid5(PROFILE_NAMESPACE, profile_key),
            profile_key=profile_key,
            vendor="Наблюдение агента",
            model=model or board_name or "Неизвестное устройство",
            board_names=[board_name] if board_name else [],
            compatibles=compatibles,
            target=target,
            cpu_model=str(cpu.get("model") or "").strip() or None,
            cpu_architecture=str(
                cpu.get("architecture") or hardware.get("architecture") or ""
            ).strip()
            or None,
            cpu_cores=_positive_int(cpu.get("cores")),
            cpu_max_mhz=(_positive_int(cpu.get("max_khz")) or 0) // 1000 or None,
            sensor_roles={},
            origin="observed",
            verified=False,
            observation_count=0,
            first_seen_at=now,
            created_at=now,
            updated_at=now,
            catalog_version=CATALOG_VERSION,
        )
        db.add(profile)
    profile.last_seen_at = now
    profile.observation_count = int(profile.observation_count or 0) + 1
    profile.updated_at = now
    # Persist a newly learned profile before an existing identity references it.
    # Without the explicit flush PostgreSQL may issue the identity UPDATE first.
    db.flush()
    return profile


def _resolved_hardware(
    hardware: dict[str, Any], cpu: dict[str, Any], profile: HardwareProfile | None
) -> dict[str, Any]:
    architecture = cpu.get("architecture") or hardware.get("architecture")
    resolved: dict[str, Any] = {
        "state": "observed" if hardware or cpu else "unsupported",
        "model": hardware.get("model"),
        "board_name": hardware.get("board_name"),
        "compatible": _as_list(hardware.get("compatible")),
        "target": hardware.get("target"),
        "package_arch": hardware.get("package_arch"),
        "architecture": architecture,
        "cpu": {
            "observed_model": cpu.get("model"),
            "architecture": architecture,
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
            "origin": profile.origin,
            "verified": profile.verified,
            "observation_count": profile.observation_count,
        }
    return resolved


def _sensor_mapping(sensor: dict[str, Any], roles: dict[str, Any]) -> dict[str, Any]:
    sensor_type = str(sensor.get("type") or "unknown")
    sensor_id = str(sensor.get("id") or sensor_type)
    mapping = roles.get(sensor_type) or roles.get(sensor_id) or {}
    if mapping:
        return mapping
    lowered = f"{sensor_type} {sensor.get('label') or ''}".lower()
    if any(token in lowered for token in ("cpu", "soc", "thermal")):
        return {"role": None, "label": "SoC / CPU"}
    if any(token in lowered for token in ("wifi", "wlan", "radio", "phy")):
        return {"role": None, "label": "Wi-Fi радиомодуль"}
    return {"role": None, "label": sensor.get("label") or sensor_type}


def record_hardware_observation(
    db: Session, device_id: UUID, payload: dict[str, Any], observed_at: datetime
) -> dict[str, Any]:
    sync_builtin_hardware_catalog(db, observed_at)
    hardware = (
        payload.get("hardware") if isinstance(payload.get("hardware"), dict) else {}
    )
    cpu = payload.get("cpu") if isinstance(payload.get("cpu"), dict) else {}
    thermal = payload.get("thermal") if isinstance(payload.get("thermal"), dict) else {}
    profile, method, confidence = _match_profile(db, hardware)
    if profile is None:
        profile = _learn_profile(db, hardware, cpu, observed_at)
        if profile is not None:
            method, confidence = "observed-identity", 60
    elif profile.origin == "observed":
        profile.last_seen_at = observed_at
        profile.observation_count = int(profile.observation_count or 0) + 1
    resolved = _resolved_hardware(hardware, cpu, profile)
    identity = db.get(DeviceHardwareIdentity, device_id)
    if identity is None:
        identity = DeviceHardwareIdentity(device_id=device_id, updated_at=observed_at)
        db.add(identity)
    identity.profile_id = profile.id if profile else None
    identity.observed = {"hardware": hardware, "cpu": cpu}
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
        mapping = _sensor_mapping(
            sensor, sensor_roles if isinstance(sensor_roles, dict) else {}
        )
        key = str(sensor.get("id") or sensor.get("type") or "unknown")[:160]
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
                label=str(mapping.get("label"))[:160],
                subsystem=str(sensor.get("subsystem") or "thermal")[:40],
                milli_celsius=value,
                warning_milli_celsius=_positive_int(
                    sensor.get("warning_milli_celsius")
                ),
                critical_milli_celsius=_positive_int(
                    sensor.get("critical_milli_celsius")
                ),
                observed_at=observed_at,
            )
        )
    db.execute(
        delete(HardwareSensorSample).where(
            HardwareSensorSample.device_id == device_id,
            HardwareSensorSample.observed_at < observed_at - timedelta(days=45),
        )
    )
    db.flush()
    return resolved


def hardware_summary(
    db: Session, device_id: UUID, payload: dict[str, Any] | None
) -> dict[str, Any]:
    from .hardware_reporting import hardware_summary as build_summary

    return build_summary(db, device_id, payload)


def hardware_report(
    db: Session,
    device_id: UUID,
    payload: dict[str, Any] | None,
    device: Any | None = None,
) -> dict[str, Any]:
    from .hardware_reporting import hardware_report as build_report

    return build_report(db, device_id, payload, device)


__all__ = [
    "CATALOG_VERSION",
    "NETIS_NX31_PROFILE_ID",
    "hardware_summary",
    "hardware_report",
    "record_hardware_observation",
    "sync_builtin_hardware_catalog",
]
