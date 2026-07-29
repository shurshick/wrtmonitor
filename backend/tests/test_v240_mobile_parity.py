from pathlib import Path

from backend.app.services.command_registry import COMMAND_REGISTRY


ROOT = Path(__file__).resolve().parents[2]
ANDROID_SOURCES = ROOT / "android" / "app" / "src" / "main" / "java"


def test_android_exposes_current_management_contract() -> None:
    source = "\n".join(
        path.read_text(encoding="utf-8") for path in ANDROID_SOURCES.rglob("*.kt")
    )
    explicit_commands = {
        command for command in COMMAND_REGISTRY if f'"{command}"' in source
    }
    api_backed_or_replaced = {
        "agent.disconnect",  # WrtMonitorApi.disconnectDevice
        "client.set_blocked",  # folded into applyNetworkClientPolicy
        "client.set_policy",  # folded into applyNetworkClientPolicy
        "firewall.set_port_forward",  # replaced by factual UCI redirect CRUD
        "firewall.delete_port_forward",  # replaced by factual UCI redirect CRUD
    }

    assert explicit_commands | api_backed_or_replaced == set(COMMAND_REGISTRY)
    assert "firewall.set_redirect" in explicit_commands
    assert "firewall.delete_redirect" in explicit_commands
    assert "vpn.wireguard.delete_interface" in explicit_commands
    assert "vpn.openvpn.set_enabled" in explicit_commands
    assert "vpn.openvpn.export_client" in explicit_commands
    assert "wifi.status" in explicit_commands


def test_android_has_restorable_navigation_and_explicit_data_states() -> None:
    app = (
        ANDROID_SOURCES / "ru" / "wrtmonitor" / "app" / "WrtMonitorApp.kt"
    ).read_text(encoding="utf-8")
    screens = (
        ANDROID_SOURCES
        / "ru"
        / "wrtmonitor"
        / "app"
        / "ui"
        / "screens"
    )
    controls = "\n".join(
        path.read_text(encoding="utf-8")
        for path in screens.glob("*ControlScreen.kt")
    )

    assert "rememberSaveable" in app
    assert "deviceStateSaver" in app
    assert "BackHandler" in app
    assert not (screens / "RouterControlScreens.kt").exists()
    for state in ('"stale"', '"error"', '"unsupported"'):
        assert state in controls
