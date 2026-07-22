import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parent
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
    "transactions.sh",
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
    expected_version = read_text(REPO_ROOT / "VERSION").strip()
    assert AGENT.exists()
    assert source.startswith("#!/bin/sh\nset -eu")
    assert len(source.splitlines()) <= 200
    assert f'AGENT_VERSION="{expected_version}"' in source
    for name in REQUIRED_LIBS:
        assert f"load_lib {name}" in source
    assert 'main "$@"' in source


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
    for name in (
        "wrtmonitor-agent",
        "wrtmonitor.init",
        "install-openwrt.sh",
        "agent-version.txt",
        "openwrt-agent-files.txt",
    ):
        assert name in entries
    for name in REQUIRED_LIBS:
        assert f"lib/{name}" in entries


def test_sha256sums_lists_payload_files():
    sums_text = read_text(SUMS)
    for name in (
        "wrtmonitor-agent",
        "wrtmonitor.init",
        "install-openwrt.sh",
        "agent-version.txt",
        "openwrt-agent-files.txt",
    ):
        assert f"  {name}" in sums_text or f" *{name}" in sums_text
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
    forbidden = ("[[ ", '[["', "\nsource ", "mapfile", "pipefail")
    for path in [AGENT, INSTALLER, *sorted(LIB_DIR.glob("*.sh"))]:
        source = read_text(path)
        for item in forbidden:
            assert item not in source


def test_management_telemetry_contains_real_router_configuration():
    telemetry = read_text(LIB_DIR / "telemetry.sh")
    for field in (
        "ipv4_details",
        "netmask",
        "pools",
        "zonename",
        "timezone",
        "ntp_servers",
    ):
        assert field in telemetry
    assert 'uci -q get "network.$name.netmask"' in telemetry
    assert 'uci -q get "dhcp.$pool_name.leasetime"' in telemetry


def test_guest_network_does_not_use_a_fixed_demo_address():
    commands = read_text(LIB_DIR / "commands.sh")
    assert "network.wrtmonitor_guest.ipaddr=192.168.3.1" not in commands
    assert 'guest_subnet="192.168.$guest_octet.0/24"' in commands


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
    assert completed.stdout.strip() == read_text(REPO_ROOT / "VERSION").strip()


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
    payload = json.loads(completed.stdout)
    capabilities_source = read_text(LIB_DIR / "capabilities.sh")
    expected_version = int(
        capabilities_source.split('CAPABILITIES_VERSION="', 1)[1].split('"', 1)[0]
    )
    assert payload["agent"]["capabilities_version"] == expected_version
    assert payload["capabilities"]["agent.status"] is True
    assert isinstance(payload["capabilities"]["agent.update"], bool)
    assert payload["capability_details"]["agent.status"]["reason"] == "available"
    assert "maintenance.backup" in payload["capabilities"]
    assert "maintenance.sysupgrade.check" in payload["capabilities"]
    assert "maintenance.diagnostics.bundle" in payload["capabilities"]


def test_maintenance_handlers_and_multiline_json_escape_are_present():
    commands = read_text(LIB_DIR / "commands.sh")
    common = read_text(LIB_DIR / "common.sh")
    capabilities = read_text(LIB_DIR / "capabilities.sh")
    for command in (
        "maintenance.package.install",
        "maintenance.backup.create",
        "maintenance.backup.restore",
        "maintenance.sysupgrade.check",
        "maintenance.logs.read",
        "maintenance.cron.set",
        "maintenance.diagnostics.bundle",
        "maintenance.recovery.enable",
    ):
        assert command in commands
    assert 'if (NR > 1) printf "\\\\n"' in common
    assert "system package removal is not allowed" in commands
    assert "maintenance.backup) has_commands sysupgrade tar base64" in capabilities
    assert "has_commands sysupgrade tar gzip" not in capabilities


def test_capability_detection_reflects_openwrt_runtime(tmp_path: Path):
    shell = shell_path()
    if not shell:
        pytest.skip("sh is not available")
    system_root = tmp_path / "root"
    command_dir = tmp_path / "bin"
    (system_root / "proc").mkdir(parents=True)
    (system_root / "etc" / "init.d").mkdir(parents=True)
    (system_root / "etc" / "config").mkdir(parents=True)
    (system_root / "tmp").mkdir(parents=True)
    command_dir.mkdir()
    for name in ("uptime", "loadavg", "cpuinfo"):
        (system_root / "proc" / name).write_text("fixture\n", encoding="utf-8")
    (system_root / "tmp" / "dhcp.leases").write_text("", encoding="utf-8")
    for service in ("network", "dnsmasq", "firewall", "sysntpd", "wrtmonitor", "sqm"):
        path = system_root / "etc" / "init.d" / service
        path.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        path.chmod(0o755)
    for command in (
        "uci",
        "ubus",
        "jsonfilter",
        "wifi",
        "ifup",
        "ifdown",
        "ip",
        "reboot",
        "nslookup",
        "curl",
        "sha256sum",
        "nlbw",
        "apk",
        "sysupgrade",
    ):
        path = command_dir / command
        path.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        path.chmod(0o755)
    env = shell_env()
    env["PATH"] = str(command_dir) + os.pathsep + env["PATH"]
    env["WRTMONITOR_SYSTEM_ROOT"] = system_root.as_posix()
    completed = subprocess.run(
        [shell, str(AGENT), "capabilities", "--json"],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )
    payload = json.loads(completed.stdout)
    assert payload["capabilities"]["wifi.radio.configure"] is True
    assert payload["capabilities"]["wifi.manage_ssid"] is True
    assert payload["capabilities"]["wifi.schedule"] is True
    assert isinstance(payload["capabilities"]["wifi.mesh"], bool)
    assert payload["capabilities"]["maintenance.packages.read"] is True
    assert payload["capabilities"]["maintenance.packages.write"] is True
    assert payload["capabilities"]["maintenance.backup"] is True


def test_apk_maintenance_telemetry_is_normalized(tmp_path: Path):
    shell = shell_path()
    if not shell:
        pytest.skip("sh is not available")
    command_dir = tmp_path / "bin"
    command_dir.mkdir()
    apk = command_dir / "apk"
    apk.write_text(
        """#!/bin/sh
case "$*" in
  "list --installed --manifest")
    printf 'base-files 1.0\\ncurl 8.0\\n'
    ;;
  "list --upgradeable --manifest")
    printf 'curl 8.1\\n'
    ;;
esac
""",
        encoding="utf-8",
    )
    apk.chmod(0o755)
    env = shell_env()
    env["PATH"] = str(command_dir) + os.pathsep + env["PATH"]
    script = f"""
        set -eu
        . '{(LIB_DIR / "common.sh").as_posix()}'
        . '{(LIB_DIR / "capabilities.sh").as_posix()}'
        . '{(LIB_DIR / "telemetry.sh").as_posix()}'
        maintenance_json
    """
    completed = subprocess.run(
        [shell, "-c", script],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )
    payload = json.loads(completed.stdout)
    assert payload["packages"]["manager"] == "apk"
    assert payload["packages"]["installed"] == 2
    assert payload["packages"]["upgradable"] == 1
    assert payload["packages"]["upgradable_items"] == [
        {"name": "curl", "current_version": "8.0", "available_version": "8.1"}
    ]


def test_apk_package_operations_use_native_commands(tmp_path: Path):
    shell = shell_path()
    if not shell:
        pytest.skip("sh is not available")
    command_dir = tmp_path / "bin"
    command_dir.mkdir()
    apk_log = tmp_path / "apk.log"
    apk = command_dir / "apk"
    apk.write_text(
        "#!/bin/sh\nprintf '%s\\n' \"$*\" >>\"$APK_LOG\"\n",
        encoding="utf-8",
    )
    apk.chmod(0o755)
    env = shell_env()
    env["PATH"] = str(command_dir) + os.pathsep + env["PATH"]
    env["APK_LOG"] = "apk.log"
    script = f"""
        set -eu
        . '{(LIB_DIR / "capabilities.sh").as_posix()}'
        package_refresh_indexes
        package_apply install curl
        package_apply remove curl
    """
    subprocess.run([shell, "-c", script], check=True, env=env, cwd=tmp_path)
    assert apk_log.read_text(encoding="utf-8").splitlines() == [
        "update",
        "add curl",
        "del curl",
    ]


def test_config_transaction_restores_saved_uci_file(tmp_path: Path):
    shell = shell_path()
    if not shell:
        pytest.skip("sh is not available")
    system_root = tmp_path / "root"
    status_dir = tmp_path / "status"
    command_dir = tmp_path / "bin"
    config_dir = system_root / "etc" / "config"
    service_dir = system_root / "etc" / "init.d"
    config_dir.mkdir(parents=True)
    service_dir.mkdir(parents=True)
    command_dir.mkdir()
    network_config = config_dir / "network"
    network_config.write_text("original\n", encoding="utf-8")
    for name in ("uci", "wifi"):
        path = command_dir / name
        path.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        path.chmod(0o755)
    network_service = service_dir / "network"
    network_service.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    network_service.chmod(0o755)
    env = shell_env()
    env["PATH"] = str(command_dir) + os.pathsep + env["PATH"]
    env["WRTMONITOR_SYSTEM_ROOT"] = system_root.as_posix()
    env["WRTMONITOR_STATUS_DIR"] = status_dir.as_posix()
    script = f"""
        set -eu
        . '{(LIB_DIR / "common.sh").as_posix()}'
        . '{(LIB_DIR / "transactions.sh").as_posix()}'
        transaction_begin test-transaction network.set_lan 90
        printf 'changed\\n' >'{network_config.as_posix()}'
        transaction_restore test-transaction
        grep -q '^original$' '{network_config.as_posix()}'
        grep -q '^state=rolled_back$' '{(status_dir / "config-transactions" / "test-transaction" / "meta").as_posix()}'
    """
    subprocess.run([shell, "-c", script], check=True, env=env)


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
    assert "package_manager_name()" in source
    assert "apk update" in source
    assert 'apk add "$@"' in source
    assert "opkg update" in source
    assert 'opkg install "$@"' in source
    assert "--clean" in source
    assert "--remove-config" in source
    for dependency in (
        "curl",
        "jsonfilter",
        "ca-bundle",
        "uci",
        "ubus",
        "coreutils-sha256sum",
        "coreutils-base64",
    ):
        assert dependency in source
    assert "ensure_optional_dependencies()" in source
    for package in ("nlbwmon", "wireguard-tools", "openvpn-openssl", "pbr"):
        assert package in source
    assert "/etc/init.d/nlbwmon enable" in source
    assert "/etc/init.d/nlbwmon restart" in source


def test_nlbwmon_traffic_parser_uses_named_columns_and_reports_source_state():
    source = read_text(ROOT / "lib" / "telemetry.sh")
    assert 'column["mac"]' in source
    assert 'column["rx_bytes"]' in source
    assert 'column["tx_bytes"]' in source
    assert '"traffic":{"available":%s,"status":"%s"}' in source
    assert "/etc/init.d/nlbwmon start" in source


def test_agent_version_file_matches_entrypoint():
    expected_version = read_text(REPO_ROOT / "VERSION").strip()
    assert read_text(AGENT_VERSION).strip() == expected_version
    assert f'AGENT_VERSION="{expected_version}"' in read_text(AGENT)


@pytest.mark.parametrize(
    ("left", "right", "expected"),
    (
        ("0.9.0", "0.10.0", "-1"),
        ("0.10.0", "0.9.0", "1"),
        ("v0.10.1", "0.10.1", "0"),
        ("0.10.0-rc9", "0.10.0-rc10", "-1"),
        ("0.10.0-rc10", "0.10.0", "-1"),
        ("0.10.0", "0.10.0-rc10", "1"),
    ),
)
def test_agent_version_comparison_is_numeric(left, right, expected):
    shell = shell_path()
    if not shell:
        pytest.skip("sh is not available")
    script = (
        f'. "{(LIB_DIR / "update.sh").as_posix()}"; compare_versions "{left}" "{right}"'
    )
    completed = subprocess.run(
        [shell, "-c", script],
        check=True,
        capture_output=True,
        text=True,
        env=shell_env(),
    )
    assert completed.stdout == expected


def test_management_capabilities_cover_full_router_foundation():
    source = read_text(ROOT / "lib" / "capabilities.sh")
    for capability in (
        "telemetry.clients",
        "telemetry.clients.traffic",
        "wifi.set_channel",
        "wifi.set_country",
        "network.interface_restart",
        "network.restart",
        "network.wan.configure",
        "network.lan.configure",
        "clients.block",
        "clients.policy",
        "qos.sqm",
        "dhcp.set_lease",
        "dhcp.delete_lease",
        "dhcp.configure",
        "dns.configure",
        "firewall.port_forward",
        "wifi.guest",
        "telemetry.wifi.stations",
        "wifi.radio.configure",
        "wifi.manage_ssid",
        "wifi.schedule",
        "wifi.roaming",
        "wifi.mesh",
        "system.set_hostname",
        "system.restart_service",
        "system.set_timezone",
        "system.set_ntp",
        "network.ipv6.configure",
        "network.multiwan.configure",
        "network.routes.configure",
        "network.ddns.configure",
        "firewall.zones.configure",
        "firewall.rules.configure",
        "firewall.upnp.configure",
        "telemetry.perimeter",
        "vpn.wireguard.read",
        "vpn.wireguard.configure",
        "vpn.openvpn.read",
        "vpn.openvpn.configure",
        "vpn.policy.read",
        "vpn.policy.configure",
        "telemetry.vpn",
    ):
        assert capability in source
    assert '"wifi.set_password":true' not in source
    assert "capability_supported()" in source
    assert "capability_unavailable_reason()" in source


def test_management_commands_have_openwrt_handlers():
    source = read_text(ROOT / "lib" / "commands.sh")
    for command in (
        "network.set_wan",
        "network.set_lan",
        "dhcp.set_pool",
        "dns.set_servers",
        "firewall.set_port_forward",
        "firewall.delete_port_forward",
        "client.set_blocked",
        "client.set_policy",
        "qos.set_sqm",
        "wifi.set_guest",
        "wifi.set_radio",
        "wifi.add_ssid",
        "wifi.update_ssid",
        "wifi.delete_ssid",
        "wifi.set_schedule",
        "wifi.set_mesh",
        "system.set_timezone",
        "system.set_ntp",
        "network.set_ipv6",
        "network.set_multiwan",
        "network.set_route",
        "network.delete_route",
        "network.set_ddns",
        "network.set_upnp",
        "firewall.set_zone",
        "firewall.delete_zone",
        "firewall.set_forwarding",
        "firewall.delete_forwarding",
        "firewall.set_rule",
        "firewall.delete_rule",
        "vpn.wireguard.set_interface",
        "vpn.wireguard.set_peer",
        "vpn.wireguard.delete_peer",
        "vpn.wireguard.export_peer",
        "vpn.openvpn.set_client",
        "vpn.openvpn.delete_client",
        "vpn.policy.set",
        "vpn.policy.delete",
    ):
        assert f"{command})" in source
    assert 'backup_config sqm "$command_id" "$command_type"' in source
