import os
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker

from backend.app.db import Base, get_engine, init_db
from backend.app.models import Device, DeviceHardwareIdentity, HardwareProfile
from backend.app.services.hardware_catalog import (
    NETIS_NX31_PROFILE_ID,
    _match_profile,
    _resolved_hardware,
    _temperature_status,
    hardware_report,
    hardware_summary,
    record_hardware_observation,
)


class _ScalarResult:
    def __init__(self, values):
        self.values = values

    def all(self):
        return self.values


class _CatalogSession:
    def __init__(self, profiles):
        self.profiles = profiles

    def scalars(self, _statement):
        return _ScalarResult(self.profiles)


def postgres_e2e_enabled() -> bool:
    return (
        bool(os.getenv("WRTMONITOR_DATABASE_URL"))
        and os.getenv("WRTMONITOR_SKIP_E2E", "0") != "1"
    )


def reset_database() -> None:
    init_db()
    tables = ", ".join(f'"{table.name}"' for table in Base.metadata.sorted_tables)
    factory = sessionmaker(bind=get_engine(), expire_on_commit=False)
    with factory() as db:
        db.execute(text(f"TRUNCATE TABLE {tables} RESTART IDENTITY CASCADE"))
        db.commit()


def test_catalog_enriches_but_never_overwrites_observed_cpu_values():
    profile = HardwareProfile(
        id=NETIS_NX31_PROFILE_ID,
        profile_key="netis-nx31",
        vendor="Netis",
        model="NX31",
        board_names=["netis,nx31"],
        compatibles=["netis,nx31"],
        target="mediatek/filogic",
        soc_vendor="MediaTek",
        soc_model="MT7981B",
        cpu_vendor="Arm",
        cpu_model="Cortex-A53",
        cpu_architecture="aarch64",
        cpu_cores=2,
        cpu_max_mhz=1300,
        sensor_roles={},
        catalog_version=1,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    resolved = _resolved_hardware(
        {"model": "netis NX31", "architecture": "aarch64"},
        {
            "model": "arm,cortex-a53",
            "architecture": "aarch64",
            "cores": 2,
            "current_khz": 864_000,
            "max_khz": 1_300_000,
        },
        profile,
    )

    assert resolved["cpu"]["observed_model"] == "arm,cortex-a53"
    assert resolved["cpu"]["current_khz"] == 864_000
    assert resolved["cpu"]["architecture"] == "aarch64"
    assert resolved["catalog"]["soc_model"] == "MT7981B"
    assert resolved["catalog"]["cpu_model"] == "Cortex-A53"


def test_common_soc_and_target_do_not_identify_router_model():
    profile = HardwareProfile(
        id=NETIS_NX31_PROFILE_ID,
        profile_key="netis-nx31",
        vendor="Netis",
        model="NX31",
        board_names=["netis,nx31"],
        compatibles=["netis,nx31"],
        target="mediatek/filogic",
        sensor_roles={},
        catalog_version=1,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    matched, method, confidence = _match_profile(
        _CatalogSession([profile]),
        {
            "model": "Another Filogic router",
            "compatible": ["vendor,other-router", "mediatek,mt7981"],
            "target": "mediatek/filogic",
        },
    )

    assert matched is None
    assert method is None
    assert confidence == 0


def test_temperature_state_uses_only_observed_limits():
    assert _temperature_status(61_000, None, None) == "unknown"
    assert _temperature_status(61_000, 70_000, 85_000) == "normal"
    assert _temperature_status(75_000, 70_000, 85_000) == "warning"
    assert _temperature_status(90_000, 70_000, 85_000) == "critical"
    assert _temperature_status(None, 70_000, 85_000) == "stale"


@pytest.mark.skipif(not postgres_e2e_enabled(), reason="PostgreSQL E2E required")
def test_netis_identity_and_multiple_sensor_history_are_persisted():
    reset_database()
    now = datetime.now(UTC)
    device_id = uuid4()
    payload = {
        "hardware": {
            "model": "netis NX31",
            "board_name": "netis,nx31",
            "compatible": ["netis,nx31", "mediatek,mt7981"],
            "target": "mediatek/filogic",
            "architecture": "aarch64",
        },
        "cpu": {
            "model": "arm,cortex-a53",
            "architecture": "aarch64",
            "cores": 2,
            "current_khz": 1_000_000,
            "max_khz": 1_300_000,
        },
        "thermal": {
            "available": True,
            "sensors": [
                {
                    "id": "thermal_zone0",
                    "subsystem": "thermal",
                    "type": "cpu-thermal",
                    "label": "cpu-thermal",
                    "milli_celsius": 51_000,
                    "warning_milli_celsius": 70_000,
                    "critical_milli_celsius": 85_000,
                    "trip_points": [
                        {"index": "0", "type": "critical", "milli_celsius": 125_000},
                        {"index": "1", "type": "hot", "milli_celsius": 120_000},
                        {"index": "2", "type": "active", "milli_celsius": 115_000},
                        {"index": "3", "type": "active", "milli_celsius": 85_000},
                        {"index": "4", "type": "active", "milli_celsius": 60_000},
                    ],
                },
                {
                    "id": "hwmon0_temp1",
                    "subsystem": "hwmon",
                    "type": "cpu_thermal",
                    "label": "cpu_thermal temp1",
                    "milli_celsius": 50_000,
                },
                {
                    "id": "hwmon1_temp1",
                    "subsystem": "hwmon",
                    "type": "mt7915_phy0",
                    "label": "mt7915_phy0 temp1",
                    "milli_celsius": 48_000,
                },
                {
                    "id": "hwmon2_temp1",
                    "subsystem": "hwmon",
                    "type": "mt7915_phy1",
                    "label": "mt7915_phy1 temp1",
                    "milli_celsius": 47_000,
                },
            ],
        },
    }
    factory = sessionmaker(bind=get_engine(), expire_on_commit=False)
    with factory() as db:
        db.add(
            Device(
                id=device_id,
                name="NetisNX31",
                hostname="OpenWrt",
                model="netis NX31",
                firmware="OpenWrt test",
                token_hash=f"hash-{device_id}",
                status="online",
                created_at=now,
                updated_at=now,
            )
        )
        db.flush()
        record_hardware_observation(db, device_id, payload, now)
        payload["thermal"]["sensors"][0]["milli_celsius"] = 60_000
        record_hardware_observation(db, device_id, payload, now + timedelta(seconds=30))
        payload["thermal"]["sensors"][0]["milli_celsius"] = 55_000
        record_hardware_observation(db, device_id, payload, now + timedelta(minutes=1))
        summary = hardware_summary(db, device_id, payload)
        report = hardware_report(db, device_id, payload)
        db.commit()

    assert summary["catalog"]["soc_model"] == "MT7981B"
    assert summary["match"] == {
        "method": "device-tree-compatible",
        "confidence": 100,
    }
    assert len(summary["sensors"]) == 3
    assert summary["raw_sensor_count"] == 4
    soc = next(item for item in summary["sensors"] if item["key"] == "soc")
    assert soc["label"] == "SoC MediaTek MT7981B"
    assert soc["source_count"] == 2
    assert soc["min_milli_celsius"] == 50_000
    assert soc["max_milli_celsius"] == 55_000
    assert soc["sample_count"] == 4
    assert soc["thermal_status"] == "normal"
    assert report["schema"] == "wrtmonitor.hardware-report.v1"
    assert len(report["observed"]["thermal"]["sensors"][0]["trip_points"]) == 5


@pytest.mark.skipif(not postgres_e2e_enabled(), reason="PostgreSQL E2E required")
def test_x86_without_kernel_sensors_is_reported_as_unsupported():
    reset_database()
    now = datetime.now(UTC)
    device_id = uuid4()
    payload = {
        "hardware": {
            "model": "innotek GmbH VirtualBox",
            "board_name": "innotek-gmbh-virtualbox",
            "target": "x86/64",
            "architecture": "x86_64",
        },
        "cpu": {
            "model": "AMD Ryzen 7 9700X 8-Core Processor",
            "architecture": "x86_64",
            "cores": 2,
        },
        "thermal": {
            "available": False,
            "state": "unsupported",
            "sensors": [],
            "throttling": {"state": "unsupported", "active": None},
        },
    }
    factory = sessionmaker(bind=get_engine(), expire_on_commit=False)
    with factory() as db:
        db.add(
            Device(
                id=device_id,
                name="OpenWrt-x86",
                hostname="OpenWrt",
                model="innotek GmbH VirtualBox",
                firmware="OpenWrt 22.03.5",
                token_hash=f"hash-{device_id}",
                status="online",
                created_at=now,
                updated_at=now,
            )
        )
        db.flush()
        record_hardware_observation(db, device_id, payload, now)
        report = hardware_report(db, device_id, payload)
        db.commit()

    assert report["identity"]["cpu"]["architecture"] == "x86_64"
    assert report["identity"]["cpu"]["cores"] == 2
    assert report["identity"]["thermal_health"] == "unsupported"
    assert report["observed"]["thermal"]["state"] == "unsupported"


@pytest.mark.skipif(not postgres_e2e_enabled(), reason="PostgreSQL E2E required")
def test_unknown_hardware_profile_is_persisted_before_identity_reference():
    reset_database()
    now = datetime.now(UTC)
    device_id = uuid4()
    factory = sessionmaker(bind=get_engine(), expire_on_commit=False)
    with factory() as db:
        db.add(
            Device(
                id=device_id,
                name="NewRouter",
                hostname="OpenWrt",
                model="Uncatalogued Router",
                firmware="OpenWrt test",
                token_hash=f"hash-{device_id}",
                status="online",
                created_at=now,
                updated_at=now,
            )
        )
        db.add(
            DeviceHardwareIdentity(
                device_id=device_id,
                observed={},
                resolved={},
                updated_at=now,
            )
        )
        db.flush()

        resolved = record_hardware_observation(
            db,
            device_id,
            {
                "hardware": {
                    "model": "Uncatalogued Router",
                    "board_name": "example,new-router",
                    "compatible": ["example,new-router"],
                    "target": "example/target",
                },
                "cpu": {"model": "example-cpu", "cores": 4},
            },
            now,
        )
        db.commit()

        identity = db.get(DeviceHardwareIdentity, device_id)
        assert identity is not None
        assert identity.profile_id is not None
        profile = db.get(HardwareProfile, identity.profile_id)

    assert profile is not None
    assert profile.origin == "observed"
    assert resolved["catalog"]["profile_key"] == profile.profile_key
