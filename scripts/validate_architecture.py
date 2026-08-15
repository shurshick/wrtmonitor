from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LIMITS = {
    "backend/app/models.py": 100,
    "backend/app/services/commands.py": 100,
    "backend/app/services/telemetry.py": 100,
    "backend/app/web/routes.py": 100,
    "backend/app/web/routes_device.py": 300,
    "backend/app/web/routes_commands.py": 300,
    "backend/app/services/client_registry.py": 450,
    "backend/app/services/hardware_catalog.py": 350,
    "openwrt-agent/lib/commands.sh": 150,
    "openwrt-agent/lib/telemetry.sh": 100,
    "openwrt-agent/lib/update.sh": 150,
    "openwrt-agent/lib/transactions.sh": 100,
    "openwrt-agent/lib/command_network.sh": 100,
    "android/app/src/main/java/ru/wrtmonitor/app/api/WrtMonitorApi.kt": 600,
    "backend/app/static/app.css": 600,
    "backend/app/static/css/components.css": 600,
    "backend/app/static/css/responsive.css": 300,
}


def line_count(path: Path) -> int:
    return len(path.read_text(encoding="utf-8").splitlines())


def main() -> int:
    failures: list[str] = []
    for relative, limit in LIMITS.items():
        path = ROOT / relative
        if not path.exists():
            failures.append(f"missing architecture facade: {relative}")
            continue
        actual = line_count(path)
        if actual > limit:
            failures.append(f"{relative}: {actual} lines, limit {limit}")

    oversized = []
    for base, pattern in (
        (ROOT / "backend/app/domain_models", "*.py"),
        (ROOT / "backend/app/services", "*.py"),
        (ROOT / "backend/app/web", "*.py"),
        (ROOT / "openwrt-agent/lib", "*.sh"),
    ):
        for path in base.glob(pattern):
            if base.name == "domain_models":
                limit = 250
            elif base.name == "lib":
                limit = 300
            else:
                limit = 600
            if line_count(path) > limit:
                oversized.append(f"{path.relative_to(ROOT)} ({line_count(path)})")
    if oversized:
        failures.append("subsystem files exceed architecture limits: " + ", ".join(oversized))

    android_ui = ROOT / "android/app/src/main/java/ru/wrtmonitor/app/ui"
    for path in android_ui.rglob("*.kt"):
        source = path.read_text(encoding="utf-8")
        if "org.json" in source or "JSONObject" in source or "JSONArray" in source:
            failures.append(
                f"transport JSON leaked into Compose: {path.relative_to(ROOT)}"
            )
        lines = len(source.splitlines())
        if lines > 850:
            failures.append(
                f"Android UI file exceeds transitional 850-line limit: {path.relative_to(ROOT)} ({lines})"
            )
        if (
            path.name
            in {
                "ClientsControlScreen.kt",
                "WifiControlScreen.kt",
                "NetworkControlScreen.kt",
                "SystemControlScreen.kt",
                "RouterControlSupport.kt",
            }
            and "WrtMonitorApi(" in source
        ):
            failures.append(
                f"router control UI bypasses RouterRepository: {path.relative_to(ROOT)}"
            )

    api_root = ROOT / "android/app/src/main/java/ru/wrtmonitor/app/api"
    for path in api_root.glob("*.kt"):
        lines = line_count(path)
        if lines > 600:
            failures.append(
                f"Android API file exceeds 600-line limit: {path.relative_to(ROOT)} ({lines})"
            )

    screen_limits = {
        "NetworkControlScreen.kt": 800,
        "SystemControlScreen.kt": 600,
        "WifiControlScreen.kt": 650,
    }
    screens_root = android_ui / "screens"
    for filename, limit in screen_limits.items():
        path = screens_root / filename
        if not path.exists():
            failures.append(f"missing Android screen: {path.relative_to(ROOT)}")
            continue
        lines = line_count(path)
        if lines > limit:
            failures.append(
                f"Android screen exceeds architecture limit: {path.relative_to(ROOT)} ({lines}, limit {limit})"
            )

    if failures:
        print("architecture validation failed:")
        for failure in failures:
            print(f"- {failure}")
        return 1
    print(
        "architecture OK: subsystem facades are thin and transport JSON stays outside Compose"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
