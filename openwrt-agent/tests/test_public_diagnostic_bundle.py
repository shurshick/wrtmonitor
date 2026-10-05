import subprocess
from pathlib import Path

LIB = Path(__file__).resolve().parents[1] / "lib" / "diagnostics.sh"


def test_archive_collection_never_reads_private_logs_processes_or_uci(tmp_path):
    script = f"""
    set -eu
    . '{LIB.as_posix()}'
    AGENT_VERSION=0.55.5
    json_escape() {{ printf '%s' "$1"; }}
    openwrt_firmware_description() {{ printf 'OpenWrt test'; }}
    cat() {{ printf 'TestModel'; }}
    diagnostics_checks_json() {{ printf '{{"server":{{"status":"ok"}}}}'; }}
    package_list_installed() {{ printf 'curl 1.0'; }}
    capabilities_json() {{ printf '{{"diagnostics.run":true}}'; }}
    uci() {{ printf 'private-psk'; exit 1; }}
    ps() {{ printf 'Authorization: private-token'; exit 1; }}
    logread() {{ printf 'password=private-password'; exit 1; }}
    write_public_diagnostic_files '{tmp_path.as_posix()}'
    """
    subprocess.run(["sh", "-c", script], check=True, capture_output=True)
    assert {item.name for item in tmp_path.iterdir()} == {
        "version.json", "diagnostics.json", "packages.txt", "capabilities.json", "README.txt"
    }
    content = "".join(item.read_text() for item in tmp_path.iterdir())
    assert "private-" not in content
    assert "TestModel" in content
