from __future__ import annotations

from backend.app.services.commands import validate_command_payload
from backend.app.services.firmware_catalog import firmware_catalog
from backend.app.services.policy_catalog import policy_catalog
from backend.app.services.telemetry import normalize_maintenance_summary
from backend.app.services.wan_events import _mwan_state


def test_sqm_profile_and_schedule_are_normalized():
    payload = validate_command_payload(
        "qos.set_sqm",
        {
            "enabled": True,
            "interface": "wan",
            "download_kbps": 100_000,
            "upload_kbps": 20_000,
            "profile": "gaming",
            "qdisc": "cake",
            "script": "layer_cake.qos",
            "qdisc_options": "diffserv4 dual-srchost nat",
            "schedule": {
                "enabled": True,
                "weekdays": ["mon", "fri"],
                "start": "18:00",
                "stop": "23:30",
            },
        },
    )

    assert payload["profile"] == "gaming"
    assert payload["schedule"] == {
        "enabled": True,
        "weekdays": ["mon", "fri"],
        "start": "18:00",
        "stop": "23:30",
    }


def test_policy_catalog_exposes_only_supported_presets():
    catalog = policy_catalog()

    assert {item["id"] for item in catalog["sqm_profiles"]} == {
        "balanced",
        "gaming",
        "streaming",
    }
    assert {item["provider"] for item in catalog["dns_policy_presets"]} == {
        "none",
        "cloudflare-security",
        "cloudflare-family",
    }
    assert {item["id"] for item in catalog["client_policy_presets"]} == {
        "unrestricted",
        "child",
        "guest",
        "iot",
    }
    assert [item["value"] for item in catalog["client_speed_options"]] == [
        0,
        1000,
        5000,
        10000,
        25000,
        50000,
        100000,
        250000,
        500000,
        1000000,
    ]


def test_mwan_state_keeps_runtime_member_order_and_roles():
    state = _mwan_state(
        {
            "perimeter": {
                "mwan3": {
                    "enabled": True,
                    "service": "running",
                    "status": "wan online\nbackup offline",
                    "members": [
                        {"role": "primary", "interface": "wan", "metric": 10},
                        {"role": "backup", "interface": "wan2", "metric": 20},
                    ],
                }
            }
        }
    )

    assert state["status"] == "wan online backup offline"
    assert state["members"][1] == {
        "role": "backup",
        "interface": "wan2",
        "metric": 20,
    }


def test_firmware_catalog_uses_reported_board_and_official_sysupgrade(monkeypatch):
    overview = {
        "branches": {
            "24.10": {
                "enabled": True,
                "targets": {"mediatek/filogic": "aarch64_cortex-a53"},
                "versions": ["24.10.2", "24.10.1", "24.10.0"],
            }
        }
    }
    profiles = {
        "profiles": {
            "vendor_router": {
                "supported_devices": ["vendor,router"],
                "titles": [{"vendor": "Vendor", "model": "Router"}],
                "images": [
                    {
                        "name": "openwrt-router-sysupgrade.bin",
                        "sha256": "a" * 64,
                        "type": "sysupgrade",
                    },
                    {
                        "name": "openwrt-router-factory.bin",
                        "sha256": "b" * 64,
                        "type": "factory",
                    },
                ],
            }
        }
    }

    monkeypatch.setattr(
        "backend.app.services.firmware_catalog._overview", lambda: overview
    )
    monkeypatch.setattr(
        "backend.app.services.firmware_catalog._profiles",
        lambda version, target: profiles
        if (version, target) == ("24.10.2", "mediatek/filogic")
        else {},
    )
    catalog = firmware_catalog(
        {
            "board": {
                "board_name": "vendor,router",
                "release": {
                    "version": "24.10.0",
                    "target": "mediatek/filogic",
                },
            }
        }
    )

    assert catalog["status"] == "observed"
    assert catalog["installed_version"] == "24.10.0"
    assert catalog["available_version"] == "24.10.2"
    assert [image["name"] for image in catalog["images"]] == [
        "openwrt-router-sysupgrade.bin"
    ]
    assert catalog["images"][0]["model"] == "vendor,router"
    assert catalog["images"][0]["url"].startswith(
        "https://downloads.openwrt.org/releases/24.10.2/"
    )


def test_firmware_catalog_reports_current_release_without_false_error(monkeypatch):
    monkeypatch.setattr(
        "backend.app.services.firmware_catalog._overview",
        lambda: {
            "branches": {
                "25.12": {
                    "enabled": True,
                    "targets": {"mediatek/filogic": "aarch64_cortex-a53"},
                    "versions": ["25.12.5", "25.12.4"],
                }
            }
        },
    )
    catalog = firmware_catalog(
        {
            "board": {
                "board_name": "netis,nx31",
                "release": {"version": "25.12.5", "target": "mediatek/filogic"},
            }
        }
    )
    assert catalog["status"] == "observed"
    assert catalog["images"] == []
    assert "already installed" in catalog["error"]


def test_openwrt_module_command_is_allowlisted_and_normalized():
    assert validate_command_payload(
        "maintenance.module.configure",
        {"module": "smb", "action": "install"},
    ) == {"module": "smb", "action": "install"}


def test_module_telemetry_drops_empty_records_and_preserves_state():
    summary = normalize_maintenance_summary(
        {
            "modules": {
                "state": "observed",
                "items": [
                    {
                        "id": "storage",
                        "supported": True,
                        "installed": True,
                        "hardware_count": 2,
                    },
                    {},
                ],
                "hardware": {"block_devices": "sda sda1"},
            }
        }
    )

    assert summary["modules_state"] == "observed"
    assert summary["modules"] == [
        {
            "id": "storage",
            "supported": True,
            "installed": True,
            "running": False,
            "enabled": False,
            "hardware_count": 2,
            "primary_package": "",
        }
    ]
    assert summary["module_hardware"]["block_devices"] == "sda sda1"
