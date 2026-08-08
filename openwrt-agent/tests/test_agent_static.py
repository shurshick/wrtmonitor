import json
import os
import shutil
import subprocess
import base64
import time
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
ED25519_PUBLIC_KEY = ROOT / "update-ed25519-public-key.pem"
RSA_PUBLIC_KEY = ROOT / "update-rsa-public-key.pem"
LEGACY_RSA_PUBLIC_KEY = ROOT / "update-rsa-legacy-public-key.pem"
REQUIRED_LIBS = [
    "common.sh",
    "dependencies.sh",
    "status.sh",
    "update.sh",
    "telemetry_system.sh",
    "telemetry_maintenance.sh",
    "telemetry_vpn.sh",
    "telemetry_network.sh",
    "telemetry_wifi.sh",
    "telemetry.sh",
    "capabilities.sh",
    "diagnostics.sh",
    "transactions.sh",
    "commands.sh",
    "idempotency.sh",
    "verification.sh",
    "command_runtime.sh",
    "command_wifi.sh",
    "command_network.sh",
    "command_firewall.sh",
    "command_vpn.sh",
    "command_system.sh",
    "command_maintenance.sh",
    "command_agent.sh",
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


def library_sources(prefix: str) -> str:
    return "\n".join(read_text(path) for path in sorted(LIB_DIR.glob(f"{prefix}*.sh")))


def source_libraries(prefix: str) -> str:
    return "\n".join(
        f". '{path.as_posix()}'" for path in sorted(LIB_DIR.glob(f"{prefix}*.sh"))
    )


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


def test_init_script_uses_procd_instead_of_a_stale_pid_file():
    source = read_text(ROOT / "wrtmonitor.init")
    assert "USE_PROCD=1" in source
    assert "start_service()" in source
    assert "procd_set_param command /usr/bin/wrtmonitor-agent daemon" in source
    assert "procd_set_param term_timeout 40" in source
    assert "procd_set_param respawn" in source
    assert "PID_FILE" not in source


def test_lan_postcondition_checks_static_address_and_netmask():
    source = read_text(ROOT / "lib" / "verification.sh")
    assert "network.set_lan)" in source
    assert 'verify_uci_value "network.$interface.proto" static' in source
    assert 'actual_ip="${actual%%/*}"' in source
    assert 'expected_prefix="$(ipv4_netmask_prefix "$netmask"' in source
    assert '[ "$actual_prefix" = "$expected_prefix" ]' in source


def test_lan_noop_does_not_restart_the_network_stack():
    source = read_text(ROOT / "lib" / "command_network.sh")
    assert "transaction_noop=1" in source
    assert "LAN configuration already matches" in source
    assert 'network_interface_cycle "$lan_interface"' in source
    assert "(sleep 3; /etc/init.d/network restart)" not in source


def test_uci_verifier_does_not_clobber_postcondition_values():
    verification = read_text(ROOT / "lib" / "verification.sh")
    helper = verification.split("postcondition_mode_for_command()", 1)[0]

    assert 'verify_uci_key="$1"' in helper
    assert 'verify_uci_expected="$2"' in helper
    assert "verify_uci_actual=" in helper
    assert '\n    expected="$2"' not in helper
    assert "\n    actual=" not in helper


def test_dns_server_postcondition_checks_dhcp_values_not_unrelated_network_config():
    source = read_text(ROOT / "lib" / "verification.sh")
    assert "dns.set_servers) verify_uci_package dhcp" in source
    assert "dns.set_servers) verify_uci_package network" not in source
    assert "actual=\"$(uci -q get 'dhcp.@dnsmasq[0].server'" in source


def test_run_lock_survives_command_substitutions_and_tracks_owner_pid():
    common = read_text(LIB_DIR / "common.sh")
    api = read_text(LIB_DIR / "api.sh")
    assert 'printf \'%s\\n\' "$$" >"$RUN_LOCK_DIR/pid"' in common
    assert "trap 'release_run_lock; exit 0' INT TERM HUP" in common
    acquire_source = common.split("acquire_lock()", 1)[1].split(
        "release_run_lock()", 1
    )[0]
    assert " EXIT " not in acquire_source
    assert api.count("release_run_lock") >= 2


def test_postcondition_verification_preserves_terminal_command_status():
    verification = (LIB_DIR / "verification.sh").read_text(encoding="utf-8")
    commands = (LIB_DIR / "commands.sh").read_text(encoding="utf-8")

    assert "verification_status=$?" in verification
    assert not any(line.strip() == "status=$?" for line in verification.splitlines())
    assert 'command_payload="${3:-{}}"' not in commands
    assert '"^${package}([|[:space:]]|$)"' in verification


def test_telemetry_does_not_send_raw_wireless_configuration():
    telemetry = (LIB_DIR / "telemetry.sh").read_text(encoding="utf-8")

    assert '"wireless_status"' not in telemetry
    assert "ubus_json network.wireless status" not in telemetry


def test_manifest_remains_compatible_with_legacy_updater():
    entries = [
        line.strip()
        for line in read_text(MANIFEST).splitlines()
        if line.strip() and not line.startswith("#")
    ]
    sums_text = read_text(SUMS)

    # Agents before signed manifests verify every listed payload file against
    # SHA256SUMS. The detached signature is downloaded separately by current
    # agents and cannot checksum itself without creating a circular manifest.
    assert "SHA256SUMS.sig" not in entries
    assert "SHA256SUMS.rsa.sig" not in entries
    assert 'download_file "$base/SHA256SUMS.sig"' in read_text(LIB_DIR / "update.sh")
    assert 'download_file "$base/SHA256SUMS.sig"' in read_text(INSTALLER)
    assert 'download_file "$base/SHA256SUMS.rsa.sig"' in read_text(
        LIB_DIR / "update.sh"
    )
    assert 'download_file "$base/SHA256SUMS.rsa.sig"' in read_text(INSTALLER)
    for name in entries:
        if name == "SHA256SUMS.txt":
            continue
        assert f"  {name}" in sums_text or f" *{name}" in sums_text


def test_nlbwmon_runtime_repairs_empty_config_and_starts_service(tmp_path: Path):
    shell = shell_path()
    if not shell:
        pytest.skip("sh is not available")
    system_root = tmp_path / "root"
    init_dir = system_root / "etc" / "init.d"
    init_dir.mkdir(parents=True)
    init_log = tmp_path / "nlbwmon-init.log"
    uci_log = tmp_path / "uci.log"
    init_script = init_dir / "nlbwmon"
    init_script.write_text(
        '#!/bin/sh\nprintf "%s\\n" "$1" >>"$NLBW_INIT_LOG"\nexit 0\n',
        encoding="utf-8",
    )
    init_script.chmod(0o755)
    env = shell_env()
    env["WRTMONITOR_SYSTEM_ROOT"] = system_root.as_posix()
    env["NLBW_INIT_LOG"] = init_log.as_posix()
    env["UCI_LOG"] = uci_log.as_posix()
    script = f"""
        set -eu
        . '{(LIB_DIR / "common.sh").as_posix()}'
        . '{(LIB_DIR / "dependencies.sh").as_posix()}'
        uci() {{
            printf '%s\\n' "$*" >>"$UCI_LOG"
            case "$*" in
                "-q get nlbwmon.@nlbwmon[0]") return 1 ;;
                "-q get nlbwmon.@nlbwmon[0].local_network") return 1 ;;
                "add nlbwmon nlbwmon") printf 'cfgfixture\\n' ;;
            esac
            return 0
        }}
        nlbw() {{ return 0; }}
        ensure_nlbwmon_runtime
    """
    subprocess.run([shell, "-c", script], check=True, env=env)
    uci_calls = uci_log.read_text(encoding="utf-8")
    assert "add nlbwmon nlbwmon" in uci_calls
    for network in ("192.168.0.0/16", "172.16.0.0/12", "10.0.0.0/8", "lan"):
        assert f"add_list nlbwmon.@nlbwmon[0].local_network={network}" in uci_calls
    assert init_log.read_text(encoding="utf-8").splitlines() == [
        "enable",
        "restart",
        "running",
    ]


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


def test_bash_script_reports_the_protocol_success_status():
    source = read_text(LIB_DIR / "command_agent.sh")
    assert "agent.bash_script)" in source
    assert 'status="completed"' not in source


def test_openwrt_command_harness():
    shell = shell_path()
    if not shell:
        pytest.skip("sh is not available")
    completed = subprocess.run(
        [shell, str(ROOT / "tests" / "harness" / "run.sh")],
        check=True,
        capture_output=True,
        text=True,
        env=shell_env(),
    )
    assert "OpenWrt command harness: PASS" in completed.stdout


def test_agent_uses_explicit_load_order():
    source = read_text(AGENT)
    assert "load_lib *.sh" not in source


def test_installer_replaces_stale_connection_identity_and_probes_server():
    source = read_text(INSTALLER)
    for assignment in (
        'uci set "wrtmonitor.main.server_url=$SERVER_URL"',
        'uci set "wrtmonitor.main.device_token=$DEVICE_TOKEN"',
        'uci set "wrtmonitor.main.device_id=$DEVICE_ID"',
        'uci set "wrtmonitor.main.name=$NAME"',
    ):
        assert assignment in source
    assert "write_connection_config" in source
    assert "/usr/bin/wrtmonitor-agent send-now" in source
    assert source.index("stop_existing_agent") < source.index("install_payload\n")
    assert source.index("/usr/bin/wrtmonitor-agent send-now") < source.index(
        "/etc/init.d/wrtmonitor start"
    )


def test_daemon_handoffs_after_command_driven_update():
    source = read_text(LIB_DIR / "api.sh")
    polling = source.index('if poll_commands "$wait_seconds"; then')
    handoff = source.index('if [ "$PENDING_AGENT_EXEC" = "1" ]; then', polling)
    failure = source.index('log_notice "command long-poll failed;', polling)
    assert polling < handoff < failure


def test_daemon_long_poll_preserves_telemetry_deadline_and_backoff():
    source = read_text(LIB_DIR / "api.sh")
    assert "next_telemetry_at=$((now + $(telemetry_interval_seconds)))" in source
    assert '[ "$wait_seconds" -le 25 ] || wait_seconds=25' in source
    assert "poll_backoff=$((poll_backoff * 2))" in source
    assert "poll_commands 0" in source


def test_legacy_six_hour_update_interval_is_migrated():
    source = read_text(LIB_DIR / "update.sh")
    assert 'DEFAULT_UPDATE_INTERVAL_HOURS="1"' in source
    assert 'if [ "$hours" = "6" ]; then' in source
    assert 'hours="$DEFAULT_UPDATE_INTERVAL_HOURS"' in source


def test_no_basic_bashisms_in_agent_libs():
    forbidden = ("[[ ", '[["', "\nsource ", "mapfile", "pipefail")
    for path in [AGENT, INSTALLER, *sorted(LIB_DIR.glob("*.sh"))]:
        source = read_text(path)
        for item in forbidden:
            assert item not in source


def test_management_telemetry_contains_real_router_configuration():
    telemetry = library_sources("telemetry")
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
    commands = library_sources("command")
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
    commands = library_sources("command")
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
        {source_libraries("telemetry")}
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
        '#!/bin/sh\nprintf \'%s\\n\' "$*" >>"$APK_LOG"\n',
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
        "openssl-util",
    ):
        assert dependency in source
    assert "ensure_optional_dependencies()" in source
    for package in ("wireguard-tools", "openvpn-openssl", "pbr"):
        assert package in source
    assert "wrtmonitor-agent ensure-dependencies" in source


def test_required_dependency_manifest_covers_runtime_features():
    source = read_text(LIB_DIR / "dependencies.sh")
    for dependency in (
        "nlbw|nlbwmon",
        "sysupgrade|base-files",
        "tar|tar",
        "base64|coreutils-base64",
        "openssl|openssl-util",
        "ethtool|ethtool",
        "iwinfo|iwinfo",
        "ip|ip-full",
        "ca-bundle",
    ):
        assert dependency in source
    assert "ensure_nlbwmon_runtime" in source
    assert "nlbwmon_runtime_status" in source


def test_update_manifest_signature_is_required_and_valid(tmp_path: Path):
    shell = shell_path()
    openssl = shutil.which("openssl")
    if not shell or not openssl:
        pytest.skip("sh or openssl is not available")
    sums = tmp_path / "SHA256SUMS.txt"
    signature = tmp_path / "SHA256SUMS.sig"
    private_key = tmp_path / "private.pem"
    public_key = tmp_path / "public.pem"
    signature_binary = tmp_path / "signature.bin"
    shutil.copy2(SUMS, sums)
    subprocess.run(
        [openssl, "genpkey", "-algorithm", "ED25519", "-out", private_key],
        check=True,
    )
    subprocess.run(
        [openssl, "pkey", "-in", private_key, "-pubout", "-out", public_key],
        check=True,
    )
    subprocess.run(
        [
            openssl,
            "pkeyutl",
            "-sign",
            "-inkey",
            private_key,
            "-rawin",
            "-in",
            sums,
            "-out",
            signature_binary,
        ],
        check=True,
    )
    signature.write_bytes(base64.b64encode(signature_binary.read_bytes()) + b"\n")
    script = f'''
        set -eu
        . "{(LIB_DIR / "update.sh").as_posix()}"
        write_update_public_key() {{ cp "{public_key.as_posix()}" "$1"; }}
        verify_manifest_signature "{tmp_path.as_posix()}"
    '''
    subprocess.run([shell, "-c", script], check=True, env=shell_env())
    sums.write_text(sums.read_text(encoding="utf-8") + "tampered\n", encoding="utf-8")
    completed = subprocess.run([shell, "-c", script], env=shell_env())
    assert completed.returncode != 0


def test_rsa_manifest_signature_supports_legacy_openssl_path(tmp_path: Path):
    shell = shell_path()
    openssl = shutil.which("openssl")
    if not shell or not openssl:
        pytest.skip("sh or openssl is not available")
    sums = tmp_path / "SHA256SUMS.txt"
    signature = tmp_path / "SHA256SUMS.rsa.sig"
    private_key = tmp_path / "private.pem"
    public_key = tmp_path / "public.pem"
    signature_binary = tmp_path / "signature.bin"
    shutil.copy2(SUMS, sums)
    subprocess.run(
        [openssl, "genpkey", "-algorithm", "RSA", "-out", private_key],
        check=True,
    )
    subprocess.run(
        [openssl, "pkey", "-in", private_key, "-pubout", "-out", public_key],
        check=True,
    )
    subprocess.run(
        [
            openssl,
            "dgst",
            "-sha256",
            "-sign",
            private_key,
            "-out",
            signature_binary,
            sums,
        ],
        check=True,
    )
    signature.write_bytes(base64.b64encode(signature_binary.read_bytes()) + b"\n")
    script = f'''
        set -eu
        . "{(LIB_DIR / "update.sh").as_posix()}"
        write_update_rsa_public_key() {{ cp "{public_key.as_posix()}" "$1"; }}
        verify_manifest_signature "{tmp_path.as_posix()}"
    '''
    subprocess.run([shell, "-c", script], check=True, env=shell_env())
    sums.write_text(sums.read_text(encoding="utf-8") + "tampered\n", encoding="utf-8")
    completed = subprocess.run([shell, "-c", script], env=shell_env())
    assert completed.returncode != 0


def test_rsa_manifest_signature_accepts_legacy_trust_key(tmp_path: Path):
    shell = shell_path()
    openssl = shutil.which("openssl")
    if not shell or not openssl:
        pytest.skip("sh or openssl is not available")
    sums = tmp_path / "SHA256SUMS.txt"
    signature = tmp_path / "SHA256SUMS.rsa.sig"
    private_key = tmp_path / "legacy-private.pem"
    public_key = tmp_path / "legacy-public.pem"
    signature_binary = tmp_path / "legacy-signature.bin"
    shutil.copy2(SUMS, sums)
    subprocess.run(
        [openssl, "genpkey", "-algorithm", "RSA", "-out", private_key], check=True
    )
    subprocess.run(
        [openssl, "pkey", "-in", private_key, "-pubout", "-out", public_key],
        check=True,
    )
    subprocess.run(
        [
            openssl,
            "dgst",
            "-sha256",
            "-sign",
            private_key,
            "-out",
            signature_binary,
            sums,
        ],
        check=True,
    )
    signature.write_bytes(base64.b64encode(signature_binary.read_bytes()) + b"\n")
    script = f'''
        set -eu
        . "{(LIB_DIR / "update.sh").as_posix()}"
        write_update_rsa_public_key() {{ printf '%s\n' invalid >"$1"; }}
        write_update_legacy_rsa_public_key() {{ cp "{public_key.as_posix()}" "$1"; }}
        verify_manifest_signature "{tmp_path.as_posix()}"
    '''
    subprocess.run([shell, "-c", script], check=True, env=shell_env())


@pytest.mark.parametrize(
    "release_key", [ED25519_PUBLIC_KEY, RSA_PUBLIC_KEY, LEGACY_RSA_PUBLIC_KEY]
)
def test_embedded_update_key_matches_release_key(release_key: Path):
    expected = read_text(release_key).strip()
    for source in (read_text(LIB_DIR / "update.sh"), read_text(INSTALLER)):
        assert expected in source


def test_installer_stops_all_stale_agent_processes_before_reinstall():
    source = read_text(INSTALLER)
    assert 'old_pids="$(pidof wrtmonitor-agent' in source
    assert "for old_pid in $old_pids" in source
    assert "rm -rf /tmp/wrtmonitor-agent.lock" in source


def test_disabled_pbr_does_not_turn_a_valid_policy_write_into_failure():
    common = read_text(LIB_DIR / "common.sh")
    vpn = read_text(LIB_DIR / "command_vpn.sh")
    transactions = read_text(LIB_DIR / "transactions.sh")
    assert "service_restart_if_enabled()" in common
    assert "service_restart_if_enabled pbr config.enabled pbr" in vpn
    assert "service_restart_if_enabled pbr config.enabled pbr" in transactions


def test_terminal_command_result_is_cached_for_replay(tmp_path: Path):
    shell = shell_path()
    if not shell:
        pytest.skip("sh is not available")
    status_dir = tmp_path / "status"
    command_id = "12345678-1234-1234-1234-123456789abc"
    script = f'''
        set -eu
        export WRTMONITOR_STATUS_DIR="{status_dir.as_posix()}"
        . "{(LIB_DIR / "common.sh").as_posix()}"
        . "{(LIB_DIR / "idempotency.sh").as_posix()}"
        api() {{ return 0; }}
        ensure_state_dirs
        report_command_result "{command_id}" success '{{"changed":true}}'
        cached_command_result "{command_id}"
    '''
    completed = subprocess.run(
        [shell, "-c", script],
        check=True,
        capture_output=True,
        text=True,
        env=shell_env(),
    )
    assert json.loads(completed.stdout) == {
        "status": "success",
        "result": {"message": "command already completed; duplicate suppressed"},
    }


def test_command_execution_does_not_run_competing_telemetry_refresh():
    commands = read_text(LIB_DIR / "commands.sh")
    transactions = read_text(LIB_DIR / "transactions.sh")
    assert 'report_command_result "$command_id" "$status" "$result"' in commands
    assert 'report_command_result "$command_id" success "$result"' in transactions
    assert "refresh_state_after_command" not in commands
    assert "refresh_state_after_command" not in transactions


def test_service_action_stops_a_hung_init_script(tmp_path: Path):
    shell = shell_path()
    if not shell:
        pytest.skip("sh is not available")
    service_dir = tmp_path / "etc" / "init.d"
    service_dir.mkdir(parents=True)
    hung_service = service_dir / "dnsmasq"
    hung_service.write_text("#!/bin/sh\nwhile :; do :; done\n", encoding="utf-8")
    hung_service.chmod(0o755)
    script = f'''
        . "{(LIB_DIR / "common.sh").as_posix()}"
        export WRTMONITOR_SYSTEM_ROOT="{tmp_path.as_posix()}"
        service_action dnsmasq restart 1
        test "$?" -eq 124
    '''
    started = time.monotonic()
    completed = subprocess.run(
        [shell, "-c", script],
        capture_output=True,
        text=True,
        env=shell_env(),
        timeout=5,
    )
    assert completed.returncode == 0, completed.stderr
    assert time.monotonic() - started < 4


def test_dns_management_uses_bounded_service_actions():
    network = read_text(LIB_DIR / "command_network.sh")
    runtime = read_text(LIB_DIR / "command_runtime.sh")
    transactions = read_text(LIB_DIR / "transactions.sh")
    assert "service_action dnsmasq restart 20" in network
    assert "service_action dnsmasq restart 20" in runtime
    assert "service_action dnsmasq restart 20" in transactions
    assert "/etc/init.d/dnsmasq restart" not in runtime


def test_nlbwmon_traffic_parser_uses_named_columns_and_reports_source_state():
    source = library_sources("telemetry")
    dependencies = read_text(LIB_DIR / "dependencies.sh")
    assert 'column["mac"]' in source
    assert 'column["rx_bytes"]' in source
    assert 'column["tx_bytes"]' in source
    assert '"traffic":{"available":%s,"status":"%s","records":%s' in source
    assert '"recovery_attempted":%s' in source
    assert "ensure_nlbwmon_runtime" in source
    assert "nlbw -c csv -g mac -o mac -n -q" in dependencies
    assert "nlbw -c csv -g mac -n -q -s ';'" not in dependencies
    assert "awk -F '\\t'" in source
    assert 'traffic_status="invalid_output"' in source


def test_nlbwmon_traffic_parser_reads_real_tab_separated_counters(tmp_path: Path):
    shell = shell_path()
    if not shell:
        pytest.skip("sh is not available")
    init_script = tmp_path / "etc" / "init.d" / "nlbwmon"
    init_script.parent.mkdir(parents=True)
    init_script.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    init_script.chmod(0o755)
    script = f"""
        set -eu
        . '{(LIB_DIR / "common.sh").as_posix()}'
        . '{(LIB_DIR / "telemetry_network.sh").as_posix()}'
        export WRTMONITOR_SYSTEM_ROOT='{tmp_path.as_posix()}'
        nlbw() {{ return 0; }}
        ip() {{ return 0; }}
        nlbwmon_runtime_status() {{ printf ready; }}
        nlbw_query_csv() {{
            printf 'mac\tconns\trx_bytes\trx_pkts\ttx_bytes\ttx_pkts\n'
            printf '02:11:22:33:44:55\t3\t1234\t4\t5678\t6\n'
        }}
        dhcp_json() {{ printf '{{"leases":[],"static_leases":[],"pools":[]}}'; }}
        clients_json
    """
    completed = subprocess.run(
        [shell, "-c", script],
        check=True,
        capture_output=True,
        text=True,
        env=shell_env(),
    )
    payload = json.loads(completed.stdout)
    assert payload["traffic"] == {
        "available": True,
        "status": "ready",
        "records": 1,
        "installed": True,
        "service": "running",
        "recovery_attempted": False,
        "error": "",
    }
    assert payload["neighbours"] == [
        {
            "mac": "02:11:22:33:44:55",
            "state": "traffic",
            "rx_bytes": 1234,
            "tx_bytes": 5678,
        }
    ]


def test_wifi_survey_reports_observed_driver_values():
    shell = shell_path()
    if not shell:
        pytest.skip("sh is not available")
    script = f"""
        set -eu
        . '{(LIB_DIR / "common.sh").as_posix()}'
        {source_libraries("telemetry")}
        iw() {{
            cat <<'EOF'
Survey data from phy1-ap0
        frequency: 5180 MHz [in use]
        noise: -95 dBm
        channel active time: 1000 ms
        channel busy time: 421 ms
        channel receive time: 201 ms
        channel transmit time: 111 ms
EOF
        }}
        wifi_survey_json phy1-ap0
    """
    completed = subprocess.run(
        [shell, "-c", script],
        check=True,
        capture_output=True,
        text=True,
        env=shell_env(),
    )
    survey = json.loads(completed.stdout)
    assert survey["state"] == "observed"
    assert survey["frequency_mhz"] == 5180
    assert survey["noise_dbm"] == -95
    assert survey["utilization_percent"] == 42


def test_wifi_telemetry_reports_supported_channels_from_selected_phy():
    source = read_text(LIB_DIR / "telemetry_wifi.sh")
    assert "wifi_supported_channels_json" in source
    assert 'iw phy "phy$wiphy_index" info' in source
    assert "supported_channels" in source


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
        "dns.encrypted.install",
        "dns.dot.configure",
        "dns.doh.configure",
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
        "network.segments.configure",
        "network.vlan.configure",
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
    source = "\n".join(
        (
            read_text(ROOT / "lib" / "command_runtime.sh"),
            library_sources("command"),
        )
    )
    for command in (
        "network.set_wan",
        "network.set_lan",
        "dhcp.set_pool",
        "dns.set_servers",
        "dns.install_dot",
        "dns.install_doh",
        "dns.set_dot",
        "dns.set_doh",
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
        "network.set_segment",
        "network.delete_segment",
        "network.set_vlan",
        "network.delete_vlan",
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
    assert "dhcp.@dnsmasq[0].server=127.0.0.1#5053" in source


def test_disabling_absent_wifi_mesh_is_idempotent():
    source = read_text(ROOT / "lib" / "command_wifi.sh")
    assert '"$enabled" = false ] && [ -z "$mesh_iface"' in source
    assert 'command_success_result "Wi-Fi mesh is already disabled"' in source
    assert "transaction_noop=1" in source


def test_network_topology_telemetry_reads_live_uci_sections():
    shell = shell_path()
    if not shell:
        pytest.skip("sh is not available")
    script = f'''
        set -eu
        . "{(LIB_DIR / "common.sh").as_posix()}"
        {source_libraries("telemetry")}
        uci() {{
            [ "$1" = "-q" ] && shift
            action="$1"; key="${{2:-}}"
            if [ "$action" = show ] && [ "$key" = network ]; then
                printf '%s\n' \
                    'network.lan=interface' \
                    'network.br_lan=device' \
                    'network.vlan10=bridge-vlan'
                return 0
            fi
            if [ "$action" = show ] && [ "$key" = firewall ]; then
                printf '%s\n' 'firewall.lan=zone'
                return 0
            fi
            [ "$action" = get ] || return 1
            case "$key" in
                network.lan.proto) printf static ;;
                network.lan.device) printf br-lan ;;
                network.lan.ipaddr) printf 192.168.31.1 ;;
                network.lan.netmask) printf 255.255.255.0 ;;
                network.br_lan.type) printf bridge ;;
                network.br_lan.name) printf br-lan ;;
                network.br_lan.ports) printf 'lan1 lan2' ;;
                network.br_lan.stp) printf 1 ;;
                network.br_lan.igmp_snooping) printf 1 ;;
                network.br_lan.vlan_filtering) printf 1 ;;
                network.vlan10.device) printf br-lan ;;
                network.vlan10.vlan) printf 10 ;;
                network.vlan10.ports) printf 'lan1:u* lan2:t' ;;
                dhcp.lan.start) printf 100 ;;
                dhcp.lan.limit) printf 100 ;;
                dhcp.lan.leasetime) printf 12h ;;
                dhcp.lan.ignore) printf 0 ;;
                firewall.lan.name) printf lan ;;
                firewall.lan.network) printf lan ;;
                firewall.lan.input) printf ACCEPT ;;
                *) return 1 ;;
            esac
        }}
        network_topology_json
    '''
    completed = subprocess.run(
        [shell, "-c", script],
        check=True,
        capture_output=True,
        text=True,
        env=shell_env(),
    )
    topology = json.loads(completed.stdout)
    assert topology["segments"][0]["ip_address"] == "192.168.31.1"
    assert topology["segments"][0]["bridge_section"] == "br_lan"
    assert topology["segments"][0]["policy"] == "trusted"
    assert topology["bridges"][0]["ports"] == ["lan1", "lan2"]
    assert topology["vlans"][0] == {
        "section": "vlan10",
        "device": "br-lan",
        "vlan_id": 10,
        "ports": ["lan1:u*", "lan2:t"],
    }


def test_daemon_recovers_unfinished_transactions_after_restart():
    api = read_text(LIB_DIR / "api.sh")
    transactions = read_text(LIB_DIR / "transactions.sh")

    assert "transaction_recover_pending" in api
    assert 'case "$state" in prepared|verifying)' in transactions
    assert "transaction_has_newer_confirmed_overlap" in transactions
    assert 'transaction_set_state "$command_id" "superseded"' in transactions
    assert "transaction_restart_verification_window" in transactions
    assert "transaction_runtime_ready" in transactions
    assert 'transaction_restore "$command_id"' in transactions
    assert "agent restarted before transaction confirmation" in transactions


def test_encrypted_dns_install_restores_plain_dns_and_checks_resolution():
    runtime = read_text(LIB_DIR / "command_runtime.sh")
    network = read_text(LIB_DIR / "command_network.sh")
    verification = read_text(LIB_DIR / "verification.sh")

    assert "restore_package_dns_backup" in runtime
    assert "doh_backup_noresolv" in runtime
    assert "dns_resolution_works" in runtime
    assert "configure_doh cloudflare false" in network
    assert "configure_dot cloudflare false" in network
    assert "encrypted_dns_install_ok" in network
    assert "restore_plain_dns" in network
    assert "did not preserve working name resolution" in network
    assert "dns_resolution_works" in verification
