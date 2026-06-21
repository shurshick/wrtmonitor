import shutil
import subprocess
from pathlib import Path

import pytest


AGENT = Path(__file__).resolve().parents[1] / "wrtmonitor-agent"


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


def test_agent_hardening_is_present():
    source = agent_source()

    assert 'LOCK_DIR="/tmp/wrtmonitor-agent.lock"' in source
    assert "--connect-timeout" in source
    assert "--max-time" in source
    assert "masked_token()" in source
    assert "debug-telemetry" in source
    assert "debug-api" in source
