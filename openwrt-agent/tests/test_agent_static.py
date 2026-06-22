import shutil
import subprocess
from pathlib import Path

import pytest


AGENT = Path(__file__).resolve().parents[1] / "wrtmonitor-agent"
INSTALLER = Path(__file__).resolve().parents[1] / "install-openwrt.sh"


def agent_source() -> str:
    return AGENT.read_text(encoding="utf-8")


def test_agent_shell_syntax():
    shell = shutil.which("sh")
    if not shell:
        pytest.skip("sh is not available")

    subprocess.run([shell, "-n", str(AGENT)], check=True)


def test_agent_has_json_helpers():
    source = agent_source()

    for name in ("json_get_string", "json_get_number", "json_get_bool", "json_get_object", "require_json_tool"):
        assert f"{name}()" in source


def test_agent_uses_jsonfilter_for_api_response_fields():
    source = agent_source()

    assert "json_get_string /tmp/wrtmonitor-register-response '@.device_id'" in source
    assert 'json_get_string /tmp/wrtmonitor-commands "@[$index].id"' in source
    assert 'json_get_string /tmp/wrtmonitor-commands "@[$index].type"' in source
    assert 'json_get_object /tmp/wrtmonitor-commands "@[$index].payload"' in source
    assert 'sed -n \'s/.*"id":"' not in source
    assert 'sed -n \'s/.*"type":"' not in source


def test_agent_wifi_telemetry_is_multi_radio():
    source = agent_source()

    assert '"radios":[' in source
    assert 'wireless.@wifi-device[$index]' in source
    assert 'wireless.@wifi-iface[$iface_index]' in source


def test_agent_collects_extended_safe_telemetry():
    source = agent_source()

    for name in ("cpu_json", "storage_json", "thermal_json", "traffic_json", "processes_json"):
        assert f"{name}()" in source


def test_agent_has_disconnect_and_wifi_password_commands():
    source = agent_source()

    assert "agent.disconnect)" in source
    assert "wifi.set_password)" in source
    assert "diagnostics.run)" in source
    assert "agent_enabled()" in source


def test_agent_can_update_itself_from_its_configured_server():
    source = agent_source()

    assert "check_for_update()" in source
    assert "update_source()" in source
    assert "SHA256SUMS.txt" in source
    assert "agent-version.txt" in source
    assert "verify_checksum()" in source
    assert "prepare_backup()" in source
    assert "perform_rollback()" in source
    assert "UPDATE_LOCK_FILE=" in source
    assert "update-status" in source


def test_agent_hardening_is_present():
    source = agent_source()

    assert 'RUN_LOCK_DIR="/tmp/wrtmonitor-agent.lock"' in source
    assert "--connect-timeout" in source
    assert "--max-time" in source
    assert "masked_token()" in source
    assert "debug-telemetry" in source
    assert "debug-api" in source


def test_agent_has_capabilities_and_diagnostics_cli():
    source = agent_source()

    assert "capabilities_json()" in source
    assert "diagnostics_json()" in source
    assert "check_server_json()" in source
    assert "check_dns_json()" in source
    assert "check_route_json()" in source
    assert "check_wifi_json()" in source
    assert "dependencies_json()" in source


def test_agent_creates_wireless_backups_before_wifi_changes():
    source = agent_source()

    assert 'CONFIG_BACKUP_DIR="$STATUS_DIR/config-backups"' in source
    assert "backup_wireless_config()" in source
    assert "list_config_backups()" in source
    assert "wireless-$timestamp-$command_id.bak" in source


def test_installer_bootstraps_runtime_dependencies():
    source = INSTALLER.read_text(encoding="utf-8")

    assert "ensure_dependencies()" in source
    assert "opkg update" in source
    assert "opkg install $missing_packages" in source
    for dependency in ("curl", "jsonfilter", "ca-bundle", "uci", "ubus", "coreutils-sha256sum"):
        assert dependency in source
