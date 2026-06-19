from fastapi.testclient import TestClient

import backend.app.main as main
from backend.app.config import Settings
from backend.app.db import get_db
from backend.app.models import Device
from backend.app.main import ALLOWED_COMMANDS, SetupRequest, app


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


def test_complete_setup_flushes_user_before_audit(monkeypatch):
    class FakeSession:
        def __init__(self):
            self.events = []

        def scalar(self, statement):
            return None

        def add(self, item):
            self.events.append(("add", item.__class__.__name__))

        def flush(self):
            self.events.append(("flush", None))

        def commit(self):
            self.events.append(("commit", None))

    monkeypatch.setattr(main, "hash_password", lambda password: "hashed-password")
    db = FakeSession()
    config = Settings(
        public_server_url=None,
        database_url="postgresql+psycopg://user:password@postgres:5432/wrtmonitor",
        bind_host="0.0.0.0",
        bind_port=8080,
        jwt_secret="test-secret",
        default_locale="ru",
        allow_insecure_local=False,
    )

    response = main.complete_setup(
        SetupRequest(
            username="admin@example.com",
            password="secret-password",
            password_confirm="secret-password",
            server_url="https://monitor.example.ru",
        ),
        config,
        db,
    )

    assert response == {"server_url": "https://monitor.example.ru"}
    assert db.events == [
        ("add", "User"),
        ("flush", None),
        ("add", "AppSetting"),
        ("add", "AuditLog"),
        ("commit", None),
    ]


def test_devices_page_lists_devices(monkeypatch):
    class FakeScalars:
        def all(self):
            return [
                Device(
                    id="a0f55bcd-3a85-4d94-8a50-f62e463682b8",
                    name="HomeRouter",
                    hostname="OpenWrt",
                    model="VirtualBox",
                    firmware="OpenWrt",
                    token_hash="token",
                    status="online",
                    last_seen_at=None,
                    created_at=None,
                    updated_at=None,
                )
            ]

    class FakeSession:
        def scalars(self, statement):
            return FakeScalars()

    def fake_db():
        yield FakeSession()

    monkeypatch.setattr(main, "is_setup_required", lambda db, config: False)
    monkeypatch.setattr(main, "web_user_from_session", lambda session_token, config, db: object())
    app.dependency_overrides[get_db] = fake_db
    client = TestClient(app)
    try:
        response = client.get("/devices", cookies={"wrtmonitor_session": "token"})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert "HomeRouter" in response.text
    assert "online" in response.text


def test_devices_page_requires_web_session(monkeypatch):
    def fake_db():
        yield object()

    monkeypatch.setattr(main, "is_setup_required", lambda db, config: False)
    monkeypatch.setattr(main, "web_user_from_session", lambda session_token, config, db: None)
    app.dependency_overrides[get_db] = fake_db
    client = TestClient(app, follow_redirects=False)
    try:
        response = client.get("/devices")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 303
    assert response.headers["location"] == "/login"
