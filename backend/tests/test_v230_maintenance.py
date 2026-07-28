from backend.app.services.commands import (
    build_command_payload_from_web_form,
    validate_command_payload,
)
from backend.app.services.telemetry import normalize_maintenance_summary


def test_maintenance_commands_have_focused_payloads():
    assert validate_command_payload("maintenance.processes.read", {}) == {}
    assert validate_command_payload("maintenance.cron.read", {}) == {}
    assert validate_command_payload("maintenance.services.read", {}) == {}
    assert validate_command_payload(
        "maintenance.package.upgrade", {"package": "nlbwmon"}
    ) == {"package": "nlbwmon"}
    assert validate_command_payload(
        "maintenance.service.set", {"service": "dnsmasq", "action": "restart"}
    ) == {"service": "dnsmasq", "action": "restart"}


def test_service_action_rejects_shell_input():
    for payload in (
        {"service": "dnsmasq;reboot", "action": "restart"},
        {"service": "dnsmasq", "action": "reload;reboot"},
    ):
        try:
            validate_command_payload("maintenance.service.set", payload)
        except Exception:
            pass
        else:
            raise AssertionError("unsafe service action accepted")


def test_web_service_action_and_maintenance_summary():
    payload = build_command_payload_from_web_form(
        "maintenance.service.set", service="dnsmasq", protocol="restart"
    )
    assert payload == {"service": "dnsmasq", "action": "restart"}
    summary = normalize_maintenance_summary(
        {
            "maintenance": {
                "cron_content": "0 4 * * * /bin/true\n",
                "services": [{"name": "dnsmasq", "running": True, "enabled": True}],
                "process_snapshot": "PID USER COMMAND",
            }
        }
    )
    assert summary["cron_content"].startswith("0 4")
    assert summary["services"][0]["running"] is True
    assert summary["process_snapshot"].startswith("PID")
