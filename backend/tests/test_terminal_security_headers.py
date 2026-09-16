import pytest
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.testclient import TestClient

from backend.app.web.security_headers import SecurityHeadersMiddleware


@pytest.mark.parametrize(
    "path,allowed",
    [
        ("/devices/11111111-1111-1111-1111-111111111111?section=terminal", True),
        ("/devices/11111111-1111-1111-1111-111111111111?section=wifi", False),
        ("/login?section=terminal", False),
        ("/api/v1/devices?section=terminal", False),
    ],
)
def test_dynamic_terminal_styles_do_not_relax_script_policy(path, allowed):
    app = FastAPI()
    app.add_middleware(SecurityHeadersMiddleware)

    @app.get("/{path:path}")
    def page(path: str):
        return HTMLResponse("terminal")

    response = TestClient(app).get(path)
    csp = response.headers["Content-Security-Policy"]
    assert ("style-src-elem 'self' 'unsafe-inline'" in csp) == allowed
    assert "default-src 'self'" in csp
    assert "unsafe-eval" not in csp and "script-src" not in csp
