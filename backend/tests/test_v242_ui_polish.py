from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_maintenance_places_compact_cards_before_services() -> None:
    template = read("backend/app/templates/partials/router_maintenance.html")

    monitoring = template.index("Журналы и процессы")
    automation = template.index("Автоматизация")
    recovery = template.index("Восстановление")
    services = template.index("maintenance-card--services")
    assert monitoring < automation < recovery < services


def test_theme_bootstrap_is_external_and_runs_before_styles() -> None:
    base = read("backend/app/templates/base.html")

    bootstrap = '<script src="/static/theme-bootstrap.js"></script>'
    assert bootstrap in base
    assert base.index(bootstrap) < base.index("/static/app.css")
    assert base.index("/static/app.css") < base.index("/static/css/components.css")
    assert base.index("/static/css/components.css") < base.index(
        "/static/css/responsive.css"
    )
    assert "wrtmonitor-theme" in read("backend/app/static/theme-bootstrap.js")


def test_reboot_is_an_icon_action_in_web_and_android_lists() -> None:
    web = read("backend/app/templates/devices.html")
    android = read(
        "android/app/src/main/java/ru/wrtmonitor/app/ui/screens/DeviceListScreen.kt"
    )
    repository = read(
        "android/app/src/main/java/ru/wrtmonitor/app/data/RouterRepository.kt"
    )

    assert 'class="icon-button router-card__reboot"' in web
    assert 'aria-label="Перезагрузить роутер"' in web
    assert "Icons.Default.RestartAlt" in android
    assert '"router.reboot"' in repository
    assert "rebootTarget" in android


def test_system_load_is_explained_relative_to_cpu_capacity() -> None:
    routes = read("backend/app/web/routes_device.py")
    template = read("backend/app/templates/partials/system.html")
    android = read(
        "android/app/src/main/java/ru/wrtmonitor/app/ui/screens/DeviceDetailScreen.kt"
    )

    assert "load_capacity_percent" in routes
    assert "Нагрузка системы" in template
    assert "очередь задач" in template
    assert "loadCapacityPercent" in android
    assert "load_capacity_value" in android
