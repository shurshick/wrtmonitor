from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_web_design_tokens_are_centralized() -> None:
    base = read("backend/app/templates/base.html")
    tokens = read("backend/app/static/css/tokens.css")

    assert base.index("/static/css/tokens.css") < base.index("/static/app.css")
    for token in (
        "--color-background",
        "--color-surface-container",
        "--color-primary",
        "--color-success",
        "--color-warning",
        "--color-error",
        "--control-lg",
        "--table-row",
        "--shell-sidebar",
    ):
        assert token in tokens
    assert 'html[data-theme="light"]' in tokens


def test_device_shell_is_responsive_and_keyboard_accessible() -> None:
    base = read("backend/app/templates/base.html")
    page = read("backend/app/templates/device_detail.html")
    shell = read("backend/app/static/shell.js")
    styles = read("backend/app/static/css/web-redesign.css")

    assert 'class="skip-link"' in base
    assert 'data-app-announcer aria-live="polite"' in base
    assert "data-nav-toggle" in base
    assert "data-router-selector" in page
    assert "data-router-search" in page
    assert "data-nav-collapse" in page
    assert "app-nav-collapsed" in shell
    assert 'event.key !== "Escape"' in shell
    assert "@media (max-width: 1024px)" in styles
    assert "@media (max-width: 768px)" in styles
    assert "prefers-reduced-motion" in styles


def test_configuration_review_keeps_progress_visible() -> None:
    page = read("backend/app/templates/device_detail.html")

    assert 'id="config-preview-progress"' in page
    assert "Проверка результата и связи" in page
    assert "progress.hidden = false" in page
    assert "dialog.close();\n    form.dataset.previewConfirmed" not in page


def test_web_iconography_is_local_and_not_emoji_based() -> None:
    base = read("backend/app/templates/base.html")
    page = read("backend/app/templates/device_detail.html")
    icons = read("backend/app/static/icons.svg")

    assert "/static/icons.svg#sun" in base
    assert "☀" not in base
    assert "☾" not in read("backend/app/static/theme.js")
    assert page.count("/static/icons.svg#") >= 10
    assert '<symbol id="router"' in icons
    assert '<symbol id="wifi"' in icons


def test_browser_regression_covers_supported_shell_widths() -> None:
    smoke = read("backend/tests/browser_smoke.py")

    for width in (1920, 1440, 1366, 1024, 768, 390):
        assert f'"width": {width}' in smoke


def test_command_pagination_updates_url_before_fetch() -> None:
    pagination = read("backend/app/static/command-pagination.js")

    assert pagination.index("window.history.replaceState") < pagination.index(
        "await fetch"
    )
    assert "window.location.reload()" in pagination
    assert "journal.dataset.paginationReady = 'true'" in pagination


def test_terminal_has_one_heading_and_viewport_bounded_workspace() -> None:
    page = read("backend/app/templates/device_detail.html")
    terminal = read("backend/app/templates/partials/ssh.html")
    styles = read("backend/app/static/css/web-redesign.css")

    terminal_section = page.split("{% elif section == 'terminal' %}", 1)[1]
    terminal_section = terminal_section.split("{% endif %}", 1)[0]
    assert "section-heading" not in terminal_section
    assert terminal.count("Терминал OpenWrt") == 1
    assert "grid-template-rows: auto minmax(0, 1fr) auto" in styles
    assert "100dvh - var(--shell-topbar)" in styles
    assert ".terminal-surface { height: auto; min-height: 0; }" in styles


def test_package_search_exposes_readiness_before_interaction() -> None:
    package_search = read("backend/app/static/package-search.js")

    assert (
        'document.documentElement.dataset.packageSearchReady = "true"' in package_search
    )
