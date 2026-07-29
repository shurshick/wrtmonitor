from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def source(name: str) -> str:
    return (ROOT / "lib" / name).read_text(encoding="utf-8")


def test_module_telemetry_covers_hardware_and_network_services():
    telemetry = source("telemetry_modules.sh")

    for module in ("storage", "smb", "nfs", "ftp", "dlna", "printer", "modem"):
        assert module in telemetry
    assert "/sys/class/block" in telemetry
    assert "/dev/usb/lp" in telemetry
    assert "/dev/cdc-wdm" in telemetry


def test_module_install_uses_fixed_dependency_sets_and_postcondition():
    commands = source("command_modules.sh")
    verification = source("verification.sh")

    for package in (
        "block-mount",
        "samba4-server",
        "nfs-kernel-server",
        "vsftpd",
        "minidlna",
        "p910nd",
        "umbim",
    ):
        assert package in commands
    assert '"maintenance.module.configure"' not in commands
    assert "maintenance.module.configure)" in commands
    assert "module_state" in verification
    assert "verify_module_postcondition" in verification


def test_module_ui_is_capability_driven_on_both_surfaces():
    web = (
        ROOT.parent / "backend/app/templates/partials/router_maintenance.html"
    ).read_text(encoding="utf-8")
    android = (
        ROOT.parent
        / "android/app/src/main/java/ru/wrtmonitor/app/ui/screens/SystemControlScreen.kt"
    ).read_text(encoding="utf-8")

    assert "supports.maintenance_modules" in web
    assert 'capabilities["maintenance.modules.write"] == true' in android
    assert "maintenance.module.configure" in web
    assert "maintenance.module.configure" in android
