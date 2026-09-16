from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.testclient import TestClient

from backend.app.web.security_headers import SecurityHeadersMiddleware


def test_terminal_styles_with_real_csp_and_theme_switch():
    playwright = pytest.importorskip("playwright.sync_api")
    static = Path(__file__).resolve().parents[1] / "app" / "static"
    device_id = "11111111-1111-1111-1111-111111111111"
    styles = [
        "css/tokens.css",
        "app.css",
        "css/components.css",
        "css/responsive.css",
        "css/web-redesign.css",
        "vendor/xterm/xterm.css",
    ]
    html = (
        '<html data-theme="dark"><head>'
        + "".join(f'<link rel="stylesheet" href="/static/{name}">' for name in styles)
        + f'''</head><body>
      <section data-terminal-device="{device_id}">
        <span id="terminal-status"></span>
        <button id="btn-terminal-connect">Connect</button>
        <button id="btn-terminal-disconnect">Disconnect</button>
        <div id="terminal-container" class="terminal-surface"></div>
      </section>
      <script src="/static/vendor/xterm/xterm.js"></script>
      <script src="/static/vendor/xterm-addon-fit/xterm-addon-fit.js"></script>
      <script src="/static/web-ssh.js"></script>
      </body></html>'''
    )
    app = FastAPI()
    app.add_middleware(SecurityHeadersMiddleware)

    @app.get("/devices/{device_id}")
    def terminal_page(device_id: str):
        return HTMLResponse(html)

    response = TestClient(app).get(f"/devices/{device_id}?section=terminal")
    with playwright.sync_playwright() as runtime:
        browser = runtime.chromium.launch()
        page = browser.new_page(viewport={"width": 1366, "height": 768})
        errors = []
        page.on(
            "console",
            lambda message: errors.append(message.text)
            if message.type == "error"
            else None,
        )
        page.route_web_socket(
            "**/terminal/ws?*",
            lambda ws: ws.send('{"type":"status","status":"connected"}'),
        )

        def serve(route):
            path = route.request.url.split("audit.local", 1)[1]
            if path.startswith("/static/"):
                asset = static / path.removeprefix("/static/")
                route.fulfill(
                    body=asset.read_bytes(),
                    content_type="text/css"
                    if asset.suffix == ".css"
                    else "text/javascript",
                )
            else:
                route.fulfill(body=response.content, headers=dict(response.headers))

        page.route("http://audit.local/**", serve)
        page.goto(f"http://audit.local/devices/{device_id}?section=terminal")
        page.locator("#btn-terminal-connect").click()
        page.evaluate("""() => new Promise(resolve => {
          const terminal = document.querySelector('[data-terminal-device]').wrtmonitorTerminal;
          terminal.write('Plain text\\r\\n\\x1b[31mANSI_RED\\x1b[0m\\r\\nWWW iii 123\\r\\n', resolve);
        })""")
        for theme, width in (
            ("dark", 1366),
            ("light", 1366),
            ("light", 390),
            ("dark", 390),
        ):
            page.set_viewport_size({"width": width, "height": 844})
            page.evaluate(
                "theme => document.documentElement.dataset.theme = theme", theme
            )
            playwright.expect(page.locator(".xterm-fg-1").first).to_contain_text(
                "ANSI_RED"
            )
            result = page.locator(".xterm-rows").evaluate("""element => ({
              font: getComputedStyle(element).fontFamily,
              foreground: getComputedStyle(element).color,
              red: getComputedStyle(element.querySelector('.xterm-fg-1')).color,
              overflow: document.documentElement.scrollWidth > innerWidth,
            })""")
            assert "monospace" in result["font"], result
            assert result["red"] != result["foreground"], result
            assert result["foreground"] == "rgb(238, 244, 249)", result
            assert not result["overflow"], result
            screenshots = Path("artifacts/browser")
            screenshots.mkdir(parents=True, exist_ok=True)
            page.screenshot(
                path=str(screenshots / f"terminal-renderer-{theme}-{width}.png")
            )
        assert not errors, errors
        browser.close()
