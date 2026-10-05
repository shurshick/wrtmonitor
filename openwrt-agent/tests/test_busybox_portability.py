import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

LIB = Path(__file__).resolve().parents[1] / "lib"


def run_shell(script, env=None):
    shell = shutil.which("sh")
    if not shell:
        pytest.skip("sh is unavailable")
    return subprocess.run(
        [shell, "-c", script], capture_output=True, text=True, env=env
    )


@pytest.mark.parametrize(
    "runtime,expected",
    [
        ({"radio0": {"up": True, "interfaces": [{"section": "cfg_test"}]}}, 0),
        ({"radio0": {"up": True, "interfaces": [{"section": "cfg_test_other"}]}}, 1),
        ({"radio0": {"up": False, "interfaces": [{"section": "cfg_test"}]}}, 1),
        ({"radio1": {"up": True, "interfaces": [{"section": "cfg_test"}]}}, 1),
        ({}, 1),
    ],
)
def test_wifi_runtime_uses_structured_json_without_tr_classes(
    tmp_path, runtime, expected
):
    fixture = tmp_path / "runtime.json"
    fixture.write_text(json.dumps(runtime))
    parser = tmp_path / "jsonfilter"
    parser.write_text(
        "#!/usr/bin/env python3\n"
        "import json, sys\n"
        "data = json.load(sys.stdin).get('radio0', {})\n"
        "query = sys.argv[-1]\n"
        "if query == '@.radio0.up' and 'up' in data:\n"
        "    print(str(data['up']).lower())\n"
        "elif query == '@.radio0.interfaces[*].section':\n"
        "    for row in data.get('interfaces', []):\n"
        "        if 'section' in row: print(row['section'])\n"
    )
    parser.chmod(0o755)
    env = {**os.environ, "PATH": f"{tmp_path}:{os.environ['PATH']}"}
    result = run_shell(
        f"""
        . '{LIB / "command_wifi_runtime.sh"}'
        uci() {{ printf radio0; }}
        wifi() {{ cat '{fixture}'; }}
        sleep() {{ :; }}
        tr() {{ echo 'BusyBox classes unavailable' >&2; return 99; }}
        wifi_iface_runtime_active cfg_test
        """,
        env,
    )
    assert result.returncode == expected, result.stderr
    assert "classes unavailable" not in result.stderr


def test_mac_matching_does_not_require_tr_character_classes():
    result = run_shell(
        f"""
        . '{LIB / "command_runtime.sh"}'
        tr() {{
            case "$*" in *'[:'*) return 99 ;; esac
            command tr "$@"
        }}
        uci() {{
            case "$3" in
                'dhcp.@host[0]') printf host ;;
                'dhcp.@host[0].mac') printf aa:bb:cc:dd:ee:ff ;;
                *) return 1 ;;
            esac
        }}
        resolve_dhcp_host_by_mac AA:BB:CC:DD:EE:FF
        """
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout == "@host[0]"


def test_ethtool_duplex_does_not_require_tr_character_classes(tmp_path):
    device = tmp_path / "sys/class/net/eth0"
    device.mkdir(parents=True)
    (device / "mtu").write_text("1500\n")
    result = run_shell(
        f"""
        export WRTMONITOR_SYSTEM_ROOT='{tmp_path}'
        . '{LIB / "common.sh"}'
        . '{LIB / "telemetry_interfaces.sh"}'
        tr() {{
            case "$*" in *'[:'*) return 99 ;; esac
            command tr "$@"
        }}
        ethtool() {{ printf 'Speed: 1000Mb/s\\nDuplex: Full\\n'; }}
        network_devices_json
        """
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["eth0"]["duplex"] == "full"
