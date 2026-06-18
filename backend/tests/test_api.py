from fastapi.testclient import TestClient

import backend.app.main as main
from backend.app.db import get_db
from backend.app.main import ALLOWED_COMMANDS, app


def test_allowed_commands_are_explicit():
    assert "router.reboot" in ALLOWED_COMMANDS
    assert "shell.exec" not in ALLOWED_COMMANDS


def test_setup_status_endpoint_shape(monkeypatch):
    def fake_db():
        yield object()

    monkeypatch.setattr(main, "has_admin", lambda db: False)
    monkeypatch.setattr(main, "get_public_server_url", lambda db, config: None)
    app.dependency_overrides[get_db] = fake_db
    client = TestClient(app)
    try:
        response = client.get("/api/v1/setup/status")
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 200
    assert response.json()["setup_required"] is True
