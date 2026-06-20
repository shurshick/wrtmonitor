import os
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete
from sqlalchemy.orm import sessionmaker

import backend.app.main as application
import backend.app.web.routes as main
import backend.app.api.setup as setup_api
from backend.app.config import Settings, load_settings
from backend.app.db import get_db, get_engine, init_db
from backend.app.models import AppSetting, AuditLog, Device, DeviceCommand, DeviceTelemetry, User
from backend.app.main import app
from backend.app.web.routes import ALLOWED_COMMANDS, SetupRequest


def test_allowed_commands_are_explicit():
    assert "router.reboot" in ALLOWED_COMMANDS
    assert "shell.exec" not in ALLOWED_COMMANDS


def test_setup_status_endpoint_shape(monkeypatch):
    def fake_db():
        yield object()

    monkeypatch.setattr(setup_api, "has_admin", lambda db: False)
    monkeypatch.setattr(setup_api, "get_public_server_url", lambda db, config: None)
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
        allow_insecure_dev_defaults=False,
        enable_api_docs=False,
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


def test_api_docs_are_disabled_by_default():
    client = TestClient(app)
    response = client.get("/docs")

    assert response.status_code == 404


def clear_database():
    init_db()
    session_factory = sessionmaker(bind=get_engine(), autoflush=False, expire_on_commit=False)
    with session_factory() as session:
        for model in (DeviceCommand, DeviceTelemetry, AuditLog, Device, AppSetting, User):
            session.execute(delete(model))
        session.commit()


def test_router_registration_telemetry_and_latest_api_e2e():
    if not os.getenv("WRTMONITOR_DATABASE_URL"):
        pytest.skip("PostgreSQL E2E test requires WRTMONITOR_DATABASE_URL")
    clear_database()
    config = load_settings()
    client = TestClient(app)

    setup_response = client.post(
        "/api/v1/setup/complete",
        json={
            "username": "admin@example.com",
            "password": "secret-password",
            "password_confirm": "secret-password",
            "server_url": "http://127.0.0.1:8080" if config.allow_insecure_local else "https://monitor.example.ru",
        },
    )
    assert setup_response.status_code == 200

    login_response = client.post("/api/v1/auth/login", json={"username": "admin@example.com", "password": "secret-password"})
    assert login_response.status_code == 200
    access_token = login_response.json()["access_token"]
    admin_headers = {"Authorization": f"Bearer {access_token}"}

    provision_response = client.post(
        "/api/v1/devices/provision",
        headers=admin_headers,
        json={"name": "HomeRouter", "hostname": "OpenWrt", "model": "VirtualBox", "firmware": "OpenWrt 22.03.5"},
    )
    assert provision_response.status_code == 200
    device_id = provision_response.json()["device_id"]
    device_token = provision_response.json()["device_token"]
    agent_headers = {"Authorization": f"Bearer {device_token}"}

    register_response = client.post(
        "/api/v1/agent/register",
        json={"device_token": device_token, "name": "HomeRouter", "hostname": "OpenWrt", "model": "VirtualBox", "firmware": "OpenWrt 22.03.5"},
    )
    assert register_response.status_code == 200
    assert register_response.json()["device_id"] == device_id

    telemetry = {
        "system": {"uptime": 123, "load": "0.01", "memory": {"total_kb": 256000, "free_kb": 128000}},
        "wifi": {"available": True, "radios": [{"name": "radio0", "up": True, "channel": "6"}]},
        "network": {"interfaces": [{"name": "lan", "up": True}]},
    }
    for index in range(105):
        telemetry_response = client.post(
            "/api/v1/agent/telemetry",
            headers=agent_headers,
            json={"device_id": device_id, "telemetry": telemetry | {"sequence": index}},
        )
        assert telemetry_response.status_code == 200

    latest_response = client.get(f"/api/v1/devices/{device_id}/telemetry/latest", headers=admin_headers)
    assert latest_response.status_code == 200
    latest = latest_response.json()
    assert latest["device_id"] == device_id
    assert latest["telemetry"]["system"]["uptime"] == 123
    assert latest["telemetry"]["wifi"]["radios"][0]["name"] == "radio0"
    assert latest["telemetry"]["sequence"] == 104
    assert latest["age_seconds"] >= 0
    assert latest["is_stale"] is False
    assert latest["source"] == "agent"

    session_factory = sessionmaker(bind=get_engine(), autoflush=False, expire_on_commit=False)
    with session_factory() as session:
        count = session.query(DeviceTelemetry).filter(DeviceTelemetry.device_id == UUID(device_id)).count()
    assert count == 100
