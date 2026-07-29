from __future__ import annotations

import io
import json

from backend.app.services.commands import validate_command_payload
from backend.app.services.firmware_catalog import _profiles, firmware_catalog
from backend.app.services.policy_catalog import policy_catalog
from backend.app.services.wan_events import _mwan_state


class _Response(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        self.close()


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
    profiles = {
        "profiles": {
            "vendor,router": {
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
                ]
            }
        }
    }

    def fake_urlopen(request, timeout):
        assert request.full_url.endswith(
            "/releases/24.10.0/targets/mediatek/filogic/profiles.json"
        )
        assert timeout == 5
        return _Response(json.dumps(profiles).encode())

    _profiles.cache_clear()
    monkeypatch.setattr("backend.app.services.firmware_catalog.urlopen", fake_urlopen)
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
    assert [image["name"] for image in catalog["images"]] == [
        "openwrt-router-sysupgrade.bin"
    ]
    assert catalog["images"][0]["model"] == "vendor,router"
