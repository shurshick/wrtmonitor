from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_web_theme_is_explicit_and_persisted() -> None:
    base = read("backend/app/templates/base.html")
    bootstrap = read("backend/app/static/theme-bootstrap.js")
    theme_script = read("backend/app/static/theme.js")

    assert "data-theme-toggle" in base
    assert '<script src="/static/theme-bootstrap.js"></script>' in base
    assert "wrtmonitor-theme" in bootstrap
    assert "<script>" not in base
    assert 'localStorage.setItem("wrtmonitor-theme"' in theme_script
    assert "data-theme" in theme_script


def test_maintenance_services_are_bounded_and_scrollable() -> None:
    template = read("backend/app/templates/partials/router_maintenance.html")
    styles = read("backend/app/static/app.css")

    assert "service-list-scroll" in template
    assert "maintenance-card--services" in template
    assert ".service-list-scroll" in styles
    assert "max-height: 430px" in styles
    assert "overflow-y: auto" in styles


def test_router_list_exposes_reboot_action() -> None:
    template = read("backend/app/templates/devices.html")

    assert 'command_type" value="router.reboot"' in template
    assert 'aria-label="Перезагрузить роутер"' in template
    assert "router-card__action-label" not in template
    assert "router-card__actions" in template


def test_android_theme_choice_is_persisted() -> None:
    app = read("android/app/src/main/java/ru/wrtmonitor/app/WrtMonitorApp.kt")
    store = read("android/app/src/main/java/ru/wrtmonitor/app/data/SessionStore.kt")
    settings = read(
        "android/app/src/main/java/ru/wrtmonitor/app/ui/screens/SettingsScreen.kt"
    )

    assert "lightColorScheme" in app
    assert "darkColorScheme" in app
    assert "sessionStore.darkTheme = enabled" in app
    assert "var darkTheme: Boolean?" in store
    assert "Switch(" in settings
