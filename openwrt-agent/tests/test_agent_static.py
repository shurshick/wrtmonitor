import os
import shutil
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
AGENT = ROOT / "wrtmonitor-agent"
INSTALLER = ROOT / "install-openwrt.sh"
LIB_DIR = ROOT / "lib"
MANIFEST = ROOT / "openwrt-agent-files.txt"
SUMS = ROOT / "SHA256SUMS.txt"
AGENT_VERSION = ROOT / "agent-version.txt"
REQUIRED_LIBS = [
    "common.sh",
    "status.sh",
    "update.sh",
    "telemetry.sh",
    "capabilities.sh",
    "diagnostics.sh",
    "commands.sh",
    "api.sh",
]


def shell_path() -> str | None:
    return shutil.which("sh")


def shell_env() -> dict[str, str]:
    env = os.environ.copy()
    git_usr_bin = r"C:\Program Files\Git\usr\bin"
    env["PATH"] = git_usr_bin + os.pathsep + env.get("PATH", "")
    env["WRTMONITOR_LIB_DIR"] = str(LIB_DIR)
    return env


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_agent_entrypoint_exists_and_is_thin():
    source = read_text(AGENT)
    assert AGENT.exists()
    assert source.startswith("#!/bin/sh\nset -eu")
    assert len(source.splitlines()) <= 200
    assert 'AGENT_VERSION="0.1.1-rc9"' in source
    for name in REQUIRED_LIBS:
        assert f"load_lib {name}" in source
    assert "main \"$@\"" in source


def test_lib_directory_contains_required_modules():
    assert LIB_DIR.is_dir()
    for name in REQUIRED_LIBS:
        assert (LIB_DIR / name).is_file()


def test_manifest_lists_required_files():
    entries = [
        line.strip()
        for line in read_text(MANIFEST).splitlines()
        if line.strip() and not line.startswith("#")
    ]
    for name in ("wrtmonitor-agent", "wrtmonitor.init", "install-openwrt.sh", "agent-version.txt", "openwrt-agent-files.txt"):
        assert name in entries
    for name in REQUIRED_LIBS:
        assert f"lib/{name}" in entries


def test_sha256sums_lists_payload_files():
    sums_text = read_text(SUMS)
    for name in ("wrtmonitor-agent", "wrtmonitor.init", "install-openwrt.sh", "agent-version.txt", "openwrt-agent-files.txt"):
        assert f"  {name}" in sums_text
    for name in REQUIRED_LIBS:
        assert f"  lib/{name}" in sums_text


def test_agent_and_libs_pass_shell_syntax():
    shell = shell_path()
    if not shell:
        pytest.skip("sh is not available")
    subprocess.run([shell, "-n", str(AGENT)], check=True, env=shell_env())
    subprocess.run([shell, "-n", str(INSTALLER)], check=True, env=shell_env())
    for path in sorted(LIB_DIR.glob("*.sh")):
        subprocess.run([shell, "-n", str(path)], check=True, env=shell_env())


def test_agent_uses_explicit_load_order():
    source = read_text(AGENT)
    assert "load_lib *.sh" not in source


def test_no_basic_bashisms_in_agent_libs():
    forbidden = ("[[ ", "[[\"", "\nsource ", "mapfile", "pipefail")
    for path in [AGENT, INSTALLER, *sorted(LIB_DIR.glob("*.sh"))]:
        source = read_text(path)
        for item in forbidden:
            assert item not in source


def test_smoke_cli_version():
    shell = shell_path()
    if not shell:
        pytest.skip("sh is not available")
    completed = subprocess.run(
        [shell, str(AGENT), "version"],
        check=True,
        capture_output=True,
        text=True,
        env=shell_env(),
    )
    assert completed.stdout.strip() == "0.1.1-rc9"


def test_smoke_cli_capabilities_json():
    shell = shell_path()
    if not shell:
        pytest.skip("sh is not available")
    completed = subprocess.run(
        [shell, str(AGENT), "capabilities", "--json"],
        check=True,
        capture_output=True,
        text=True,
        env=shell_env(),
    )
    assert '"capabilities"' in completed.stdout
    assert '"agent.update":true' in completed.stdout
    assert '"agent.set_interval":true' in completed.stdout


def test_smoke_cli_diagnostics_json():
    shell = shell_path()
    if not shell:
        pytest.skip("sh is not available")
    completed = subprocess.run(
        [shell, str(AGENT), "diagnostics"],
        check=True,
        capture_output=True,
        text=True,
        env=shell_env(),
    )
    assert '"dependencies"' in completed.stdout
    assert '"wifi"' in completed.stdout


def test_installer_bootstraps_runtime_dependencies():
    source = read_text(INSTALLER)
    assert "ensure_dependencies()" in source
    assert "opkg update" in source
    assert "opkg install $missing_packages" in source
    assert "--clean" in source
    assert "--remove-config" in source
    for dependency in ("curl", "jsonfilter", "ca-bundle", "uci", "ubus", "coreutils-sha256sum"):
        assert dependency in source


def test_agent_version_file_matches_entrypoint():
    assert read_text(AGENT_VERSION).strip() == "0.1.1-rc9"
    assert 'AGENT_VERSION="0.1.1-rc9"' in read_text(AGENT)
