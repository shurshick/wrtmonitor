import base64

import pytest
from fastapi import HTTPException

from backend.app.services.commands import (
    build_command_payload_from_web_form,
    public_command_result,
    validate_command_payload,
)
from backend.app.services.telemetry import normalize_maintenance_summary


def test_maintenance_payloads_are_normalized():
    assert validate_command_payload(
        "maintenance.package.install", {"package": "tcpdump-mini"}
    ) == {"package": "tcpdump-mini"}
    firmware = validate_command_payload(
        "maintenance.sysupgrade.check",
        {
            "url": "https://downloads.openwrt.org/firmware.bin",
            "sha256": "a" * 64,
            "expected_model": "Router X",
            "preserve_config": True,
        },
    )
    assert firmware["sha256"] == "a" * 64
    assert firmware["preserve_config"] is True
    assert validate_command_payload("maintenance.logs.read", {"lines": 500}) == {
        "lines": 500
    }


@pytest.mark.parametrize("package", ["base-files", "busybox", "kernel", "uci"])
def test_system_packages_cannot_be_removed(package):
    with pytest.raises(HTTPException) as error:
        validate_command_payload("maintenance.package.remove", {"package": package})
    assert error.value.status_code == 400


@pytest.mark.parametrize(
    ("command_type", "payload"),
    [
        ("maintenance.package.install", {"package": "x;reboot"}),
        (
            "maintenance.sysupgrade.check",
            {"url": "http://example/x", "sha256": "a" * 64},
        ),
        (
            "maintenance.sysupgrade.check",
            {"url": "https://u:p@example/x", "sha256": "a" * 64},
        ),
        ("maintenance.process.signal", {"pid": 1, "signal": "KILL"}),
        ("maintenance.process.signal", {"pid": 20, "signal": "USR1"}),
    ],
)
def test_maintenance_rejects_unsafe_payloads(command_type, payload):
    with pytest.raises(HTTPException) as error:
        validate_command_payload(command_type, payload)
    assert error.value.status_code == 400


def test_backup_validation_and_artifact_redaction():
    archive = base64.b64encode(b"\x1f\x8bfixture").decode()
    assert (
        validate_command_payload(
            "maintenance.backup.restore", {"archive_base64": archive}
        )["archive_base64"]
        == archive
    )
    public = public_command_result(
        "maintenance.backup.create", {"archive_base64": archive, "filename": "x.tgz"}
    )
    assert public["archive_base64"] == "download available"


def test_web_form_and_maintenance_telemetry_summary():
    form = build_command_payload_from_web_form(
        "maintenance.sysupgrade.check",
        url="https://downloads.openwrt.org/x.bin",
        sha256="b" * 64,
        name="Router X",
    )
    assert form["expected_model"] == "Router X"
    assert normalize_maintenance_summary(
        {
            "maintenance": {
                "installed_packages": 120,
                "upgradable_packages": 3,
                "recovery_mode": True,
            }
        }
    ) == {
        "installed_packages": 120,
        "upgradable_packages": 3,
        "cron_entries": 0,
        "recovery_mode": True,
        "staged_firmware_sha256": "",
    }
