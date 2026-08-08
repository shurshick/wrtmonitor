from pathlib import Path

from scripts.generate_command_matrix import build_matrix


ROOT = Path(__file__).resolve().parents[2]
ANDROID_SOURCES = ROOT / "android" / "app" / "src" / "main" / "java"


def test_android_exposes_current_management_contract() -> None:
    matrix = build_matrix()
    android_exclusions = {
        row["command"]
        for row in matrix["commands"]
        if "android" in row.get("surface_exclusions", {})
    }

    assert matrix["command_count"] == 93
    assert all(row["surfaces"]["web"] for row in matrix["commands"])
    assert android_exclusions == {"agent.bash_script", "agent.ssh_session"}
    assert all(
        row["surfaces"]["android"] or row["command"] in android_exclusions
        for row in matrix["commands"]
    )
    assert all(row["surfaces"]["api"] for row in matrix["commands"])
    assert all(row["surfaces"]["agent"] for row in matrix["commands"])


def test_android_has_restorable_navigation_and_explicit_data_states() -> None:
    app = (
        ANDROID_SOURCES / "ru" / "wrtmonitor" / "app" / "WrtMonitorApp.kt"
    ).read_text(encoding="utf-8")
    screens = ANDROID_SOURCES / "ru" / "wrtmonitor" / "app" / "ui" / "screens"
    controls = "\n".join(
        path.read_text(encoding="utf-8") for path in screens.glob("*ControlScreen.kt")
    )

    assert "rememberSaveable" in app
    assert "deviceStateSaver" in app
    assert "BackHandler" in app
    assert not (screens / "RouterControlScreens.kt").exists()
    for state in ('"stale"', '"error"', '"unsupported"'):
        assert state in controls
