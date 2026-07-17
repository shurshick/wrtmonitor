import os
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete
from sqlalchemy.orm import sessionmaker

import backend.app.web.routes as main
import backend.app.api.setup as setup_api
import backend.app.services.setup as setup_service
from backend.app.config import Settings, load_settings
from backend.app.db import get_db, get_engine, init_db
from backend.app.models import (
    AppSetting,
    AuditLog,
    Device,
    DeviceCommand,
    DeviceTelemetry,
    User,
)
from backend.app.main import app
from backend.app.config import APP_VERSION
from backend.app.services.openwrt_downloads import ensure_openwrt_download_metadata
from backend.app.services.commands import ALLOWED_COMMANDS, public_command_payload
from backend.app.schemas import SetupRequest


def postgres_e2e_enabled() -> bool:
    return (
        bool(os.getenv("WRTMONITOR_DATABASE_URL"))
        and os.getenv("WRTMONITOR_SKIP_E2E", "0") != "1"
    )


def test_allowed_commands_are_explicit():
    assert "router.reboot" in ALLOWED_COMMANDS
    assert "agent.disconnect" in ALLOWED_COMMANDS
    assert "wifi.set_password" in ALLOWED_COMMANDS
    assert "agent.update" in ALLOWED_COMMANDS
    assert "agent.rollback" in ALLOWED_COMMANDS
    assert "agent.set_auto_update" in ALLOWED_COMMANDS
    assert "agent.set_interval" in ALLOWED_COMMANDS
    assert "shell.exec" not in ALLOWED_COMMANDS


def test_web_timestamp_filter_accepts_command_history_iso_strings():
    assert (
        main.format_timestamp("2026-07-16T10:49:59+00:00") == "16.07.2026 10:49:59 UTC"
    )


def test_password_command_payload_is_redacted_for_clients():
    assert public_command_payload("wifi.set_password", {"key": "secret-pass"}) == {
        "key": "********"
    }


def test_setup_status_endpoint_shape(monkeypatch):
    def fake_db():
        yield object()

    monkeypatch.setattr(setup_api, "is_setup_required", lambda db, config: True)
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


def test_health_config_exposes_openwrt_downloads_without_secrets():
    client = TestClient(app)
    response = client.get("/health/config")

    assert response.status_code == 200
    payload = response.json()
    assert payload["openwrt_downloads_enabled"] is True
    assert payload["openwrt_downloads_path"] == "/downloads/openwrt/"
    assert payload["access_model"] == "single-owner"
    assert "jwt_secret" not in payload


def test_openwrt_downloads_publish_metadata_files():
    ensure_openwrt_download_metadata()
    client = TestClient(app)
    version_response = client.get("/downloads/openwrt/agent-version.txt")
    sums_response = client.get("/downloads/openwrt/SHA256SUMS.txt")

    assert version_response.status_code == 200
    assert sums_response.status_code == 200
    assert "wrtmonitor-agent" in sums_response.text
    assert "wrtmonitor.init" in sums_response.text
    assert "install-openwrt.sh" in sums_response.text
    assert "agent-version.txt" in sums_response.text


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

    monkeypatch.setattr(
        setup_service, "hash_password", lambda password: "hashed-password"
    )
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

    response = setup_service.complete_setup(
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
    monkeypatch.setattr(
        main, "web_user_from_session", lambda session_token, config, db: object()
    )
    app.dependency_overrides[get_db] = fake_db
    client = TestClient(app)
    client.cookies.set("wrtmonitor_session", "token")
    try:
        response = client.get("/devices")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert "HomeRouter" in response.text
    assert "online" in response.text


def test_devices_page_allows_permanent_delete_for_every_device(monkeypatch):
    class FakeScalars:
        def all(self):
            return [
                Device(
                    id="a0f55bcd-3a85-4d94-8a50-f62e463682b8",
                    name="DisabledRouter",
                    hostname="OpenWrt",
                    model="VirtualBox",
                    firmware="OpenWrt",
                    token_hash="token",
                    status="disabled",
                    last_seen_at=None,
                    created_at=None,
                    updated_at=None,
                ),
                Device(
                    id="b0f55bcd-3a85-4d94-8a50-f62e463682b8",
                    name="OnlineRouter",
                    hostname="OpenWrt",
                    model="VirtualBox",
                    firmware="OpenWrt",
                    token_hash="token",
                    status="online",
                    last_seen_at=None,
                    created_at=None,
                    updated_at=None,
                ),
            ]

    class FakeSession:
        def scalars(self, statement):
            return FakeScalars()

    def fake_db():
        yield FakeSession()

    monkeypatch.setattr(main, "is_setup_required", lambda db, config: False)
    monkeypatch.setattr(
        main, "web_user_from_session", lambda session_token, config, db: object()
    )
    app.dependency_overrides[get_db] = fake_db
    client = TestClient(app)
    client.cookies.set("wrtmonitor_session", "token")
    try:
        response = client.get("/devices")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.text.count('aria-label="Удалить роутер"') == 2
    assert "/devices/a0f55bcd-3a85-4d94-8a50-f62e463682b8/delete" in response.text
    assert "/devices/b0f55bcd-3a85-4d94-8a50-f62e463682b8/delete" in response.text


def test_device_page_renders_agent_update_status(monkeypatch):
    device = Device(
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
    telemetry = DeviceTelemetry(
        device_id=device.id,
        payload={
            "agent": {
                "version": APP_VERSION,
                "auto_update_enabled": True,
                "available_version": APP_VERSION,
                "last_update_status": "success",
            }
        },
        created_at=datetime.now(UTC),
    )

    class FakeScalars:
        def __init__(self, items):
            self._items = items

        def first(self):
            return self._items[0] if self._items else None

        def all(self):
            return self._items

    class FakeSession:
        def __init__(self):
            self.calls = 0

        def scalars(self, statement):
            self.calls += 1
            if self.calls == 1:
                return FakeScalars([telemetry])
            return FakeScalars([])

    def fake_db():
        yield FakeSession()

    monkeypatch.setattr(main, "is_setup_required", lambda db, config: False)
    monkeypatch.setattr(
        main, "web_user_from_session", lambda session_token, config, db: object()
    )
    monkeypatch.setattr(
        main, "get_user_device_or_404", lambda db, user, device_id: device
    )
    app.dependency_overrides[get_db] = fake_db
    client = TestClient(app)
    client.cookies.set("wrtmonitor_session", "token")
    try:
        response = client.get(f"/devices/{device.id}?section=management")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert "Агент" in response.text
    assert APP_VERSION in response.text
    assert "success" in response.text


def test_device_page_collapses_capabilities_by_default(monkeypatch):
    device = Device(
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
    telemetry = DeviceTelemetry(
        device_id=device.id,
        payload={
            "agent": {
                "version": APP_VERSION,
                "capabilities": {
                    "agent.update": True,
                    "wifi.set_ssid": True,
                    "system.reboot": False,
                },
            }
        },
        created_at=datetime.now(UTC),
    )

    class FakeScalars:
        def __init__(self, items):
            self._items = items

        def first(self):
            return self._items[0] if self._items else None

        def all(self):
            return self._items

    class FakeSession:
        def scalars(self, statement):
            rendered = str(statement)
            if "device_telemetry" in rendered:
                return FakeScalars([telemetry])
            return FakeScalars([])

    def fake_db():
        yield FakeSession()

    monkeypatch.setattr(main, "is_setup_required", lambda db, config: False)
    monkeypatch.setattr(
        main, "web_user_from_session", lambda session_token, config, db: object()
    )
    monkeypatch.setattr(
        main, "get_user_device_or_404", lambda db, user, device_id: device
    )
    monkeypatch.setattr(
        main,
        "device_supports",
        lambda db, device_id, capability: telemetry.payload["agent"][
            "capabilities"
        ].get(capability, False),
    )
    app.dependency_overrides[get_db] = fake_db
    client = TestClient(app)
    client.cookies.set("wrtmonitor_session", "token")
    try:
        response = client.get(f"/devices/{device.id}?section=management")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert "2 enabled / 1 disabled" in response.text
    assert "Технические данные" in response.text
    assert "Обновление агента" in response.text
    assert "Обмен данными" in response.text
    assert "Диагностика" in response.text
    assert '<details class="technical-panel section">' in response.text


def test_devices_page_requires_web_session(monkeypatch):
    def fake_db():
        yield object()

    monkeypatch.setattr(main, "is_setup_required", lambda db, config: False)
    monkeypatch.setattr(
        main, "web_user_from_session", lambda session_token, config, db: None
    )
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
    session_factory = sessionmaker(
        bind=get_engine(), autoflush=False, expire_on_commit=False
    )
    with session_factory() as session:
        for model in (
            DeviceCommand,
            DeviceTelemetry,
            AuditLog,
            Device,
            AppSetting,
            User,
        ):
            session.execute(delete(model))
        session.commit()


def test_router_registration_telemetry_and_latest_api_e2e():
    if not postgres_e2e_enabled():
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
            "server_url": "http://127.0.0.1:8080"
            if config.allow_insecure_local
            else "https://monitor.example.ru",
        },
    )
    assert setup_response.status_code == 200

    login_response = client.post(
        "/api/v1/auth/login",
        json={"username": "admin@example.com", "password": "secret-password"},
    )
    assert login_response.status_code == 200
    access_token = login_response.json()["access_token"]
    admin_headers = {"Authorization": f"Bearer {access_token}"}

    provision_response = client.post(
        "/api/v1/devices/provision",
        headers=admin_headers,
        json={
            "name": "HomeRouter",
            "hostname": "OpenWrt",
            "model": "VirtualBox",
            "firmware": "OpenWrt 22.03.5",
        },
    )
    assert provision_response.status_code == 200
    device_id = provision_response.json()["device_id"]
    device_token = provision_response.json()["device_token"]
    agent_headers = {"Authorization": f"Bearer {device_token}"}

    register_response = client.post(
        "/api/v1/agent/register",
        json={
            "device_token": device_token,
            "name": "HomeRouter",
            "hostname": "OpenWrt",
            "model": "VirtualBox",
            "firmware": "OpenWrt 22.03.5",
        },
    )
    assert register_response.status_code == 200
    assert register_response.json()["device_id"] == device_id

    telemetry = {
        "system": {
            "uptime": 123,
            "load": "0.01",
            "memory": {"total_kb": 256000, "free_kb": 128000},
        },
        "wifi": {
            "available": True,
            "radios": [{"name": "radio0", "up": True, "channel": "6"}],
        },
        "network": {"interfaces": [{"name": "lan", "up": True}]},
        "agent": {
            "version": APP_VERSION,
            "auto_update_enabled": True,
            "last_update_status": "success",
            "last_update_error": "",
            "last_update_check": "2026-06-21T10:00:00Z",
            "last_successful_update": "2026-06-21T10:00:00Z",
            "backup_available": True,
            "available_version": APP_VERSION,
            "update_source": "https://monitor.example.ru/downloads/openwrt",
        },
    }
    for index in range(105):
        telemetry_response = client.post(
            "/api/v1/agent/telemetry",
            headers=agent_headers,
            json={"device_id": device_id, "telemetry": telemetry | {"sequence": index}},
        )
        assert telemetry_response.status_code == 200

    latest_response = client.get(
        f"/api/v1/devices/{device_id}/telemetry/latest", headers=admin_headers
    )
    assert latest_response.status_code == 200
    latest = latest_response.json()
    assert latest["device_id"] == device_id
    assert latest["telemetry"]["system"]["uptime"] == 123
    assert latest["telemetry"]["wifi"]["radios"][0]["name"] == "radio0"
    assert latest["telemetry"]["agent"]["version"] == APP_VERSION
    assert latest["telemetry"]["sequence"] == 104
    assert latest["age_seconds"] >= 0
    assert latest["is_stale"] is False
    assert latest["source"] == "agent"
    assert latest["clients"] == {"count": 0, "items": []}
    assert "system" in latest
    assert "services" in latest

    session_factory = sessionmaker(
        bind=get_engine(), autoflush=False, expire_on_commit=False
    )
    with session_factory() as session:
        count = (
            session.query(DeviceTelemetry)
            .filter(DeviceTelemetry.device_id == UUID(device_id))
            .count()
        )
    assert count == 100


def test_device_delete_removes_router_and_all_related_data():
    if not postgres_e2e_enabled():
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
            "server_url": "http://127.0.0.1:8080"
            if config.allow_insecure_local
            else "https://monitor.example.ru",
        },
    )
    assert setup_response.status_code == 200

    login_response = client.post(
        "/api/v1/auth/login",
        json={"username": "admin@example.com", "password": "secret-password"},
    )
    access_token = login_response.json()["access_token"]
    admin_headers = {"Authorization": f"Bearer {access_token}"}

    provision_response = client.post(
        "/api/v1/devices/provision",
        headers=admin_headers,
        json={
            "name": "DeleteRouter",
            "hostname": "OpenWrt",
            "model": "VirtualBox",
            "firmware": "OpenWrt 22.03.5",
        },
    )
    device_id = provision_response.json()["device_id"]
    device_token = provision_response.json()["device_token"]
    agent_headers = {"Authorization": f"Bearer {device_token}"}

    online_response = client.post(
        "/api/v1/agent/telemetry",
        headers=agent_headers,
        json={"device_id": device_id, "telemetry": {"system": {"uptime": 1}}},
    )
    assert online_response.status_code == 200
    disconnect_response = client.post(
        f"/api/v1/devices/{device_id}/disconnect",
        headers=admin_headers,
    )
    assert disconnect_response.status_code == 200
    command_id = disconnect_response.json()["command_id"]

    delete_response = client.delete(
        f"/api/v1/devices/{device_id}",
        headers=admin_headers,
    )
    assert delete_response.status_code == 200
    assert delete_response.json()["status"] == "deleted"

    deleted_telemetry_response = client.post(
        "/api/v1/agent/telemetry",
        headers=agent_headers,
        json={"device_id": device_id, "telemetry": {"system": {"uptime": 2}}},
    )
    assert deleted_telemetry_response.status_code in {401, 403}

    list_response = client.get("/api/v1/devices", headers=admin_headers)
    assert list_response.status_code == 200
    assert all(device["id"] != device_id for device in list_response.json())

    session_factory = sessionmaker(
        bind=get_engine(), autoflush=False, expire_on_commit=False
    )
    with session_factory() as session:
        device_count = (
            session.query(Device).filter(Device.id == UUID(device_id)).count()
        )
        telemetry_count = (
            session.query(DeviceTelemetry)
            .filter(DeviceTelemetry.device_id == UUID(device_id))
            .count()
        )
        command_count = (
            session.query(DeviceCommand)
            .filter(DeviceCommand.device_id == UUID(device_id))
            .count()
        )
        command_audit_count = (
            session.query(AuditLog).filter(AuditLog.object_id == command_id).count()
        )
        device_audit_count = (
            session.query(AuditLog).filter(AuditLog.object_id == device_id).count()
        )
    assert device_count == 0
    assert telemetry_count == 0
    assert command_count == 0
    assert command_audit_count == 0
    assert device_audit_count == 0


def test_command_lifecycle_retry_expiry_and_idempotent_result_e2e():
    if not postgres_e2e_enabled():
        pytest.skip("PostgreSQL E2E test requires WRTMONITOR_DATABASE_URL")
    clear_database()
    config = load_settings()
    client = TestClient(app)
    setup = client.post(
        "/api/v1/setup/complete",
        json={
            "username": "owner@example.com",
            "password": "secret-password",
            "password_confirm": "secret-password",
            "server_url": "http://127.0.0.1:8080"
            if config.allow_insecure_local
            else "https://monitor.example.ru",
        },
    )
    assert setup.status_code == 200
    login = client.post(
        "/api/v1/auth/login",
        json={"username": "owner@example.com", "password": "secret-password"},
    )
    assert login.status_code == 200
    assert login.json()["refresh_token"]
    refresh = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": login.json()["refresh_token"]},
    )
    assert refresh.status_code == 200
    owner_headers = {"Authorization": f"Bearer {refresh.json()['access_token']}"}
    provision = client.post(
        "/api/v1/devices/provision",
        headers=owner_headers,
        json={"name": "Lifecycle", "hostname": "openwrt"},
    )
    assert provision.status_code == 200
    device_id = provision.json()["device_id"]
    agent_headers = {"Authorization": f"Bearer {provision.json()['device_token']}"}
    telemetry = client.post(
        "/api/v1/agent/telemetry",
        headers=agent_headers,
        json={
            "device_id": device_id,
            "telemetry": {
                "agent": {
                    "version": APP_VERSION,
                    "capabilities": {"diagnostics.check_server": True},
                }
            },
        },
    )
    assert telemetry.status_code == 200

    def create_diagnostics() -> str:
        response = client.post(
            f"/api/v1/devices/{device_id}/commands",
            headers=owner_headers,
            json={
                "command_type": "diagnostics.run",
                "payload": {"checks": ["server"]},
                "confirmed": True,
            },
        )
        assert response.status_code == 200
        return response.json()["command_id"]

    command_id = create_diagnostics()
    polled = client.get("/api/v1/agent/commands", headers=agent_headers)
    assert polled.status_code == 200
    assert polled.json()[0]["id"] == command_id
    running = client.post(
        f"/api/v1/agent/commands/{command_id}/result",
        headers=agent_headers,
        json={"status": "running", "result": {}},
    )
    assert running.json()["status"] == "running"
    completed = client.post(
        f"/api/v1/agent/commands/{command_id}/result",
        headers=agent_headers,
        json={"status": "success", "result": {"server": {"ok": True}}},
    )
    assert completed.json()["status"] == "success"
    duplicate = client.post(
        f"/api/v1/agent/commands/{command_id}/result",
        headers=agent_headers,
        json={"status": "failed", "result": {"error": "late duplicate"}},
    )
    assert duplicate.json()["status"] == "success"

    failed_id = create_diagnostics()
    client.get("/api/v1/agent/commands", headers=agent_headers)
    failed = client.post(
        f"/api/v1/agent/commands/{failed_id}/result",
        headers=agent_headers,
        json={"status": "failed", "result": {"error": "dns unavailable"}},
    )
    assert failed.json()["status"] == "failed"

    retry_id = create_diagnostics()
    client.get("/api/v1/agent/commands", headers=agent_headers)
    session_factory = sessionmaker(
        bind=get_engine(), autoflush=False, expire_on_commit=False
    )
    with session_factory() as session:
        retry_command = session.get(DeviceCommand, UUID(retry_id))
        retry_command.updated_at = datetime.now(UTC) - timedelta(seconds=60)
        session.commit()
    retried = client.get("/api/v1/agent/commands", headers=agent_headers)
    assert retried.status_code == 200
    assert retried.json()[0]["id"] == retry_id
    history = client.get(
        f"/api/v1/devices/{device_id}/commands?limit=20", headers=owner_headers
    ).json()
    retry_entry = next(item for item in history if item["id"] == retry_id)
    assert retry_entry["status"] == "sent"
    assert retry_entry["retry_count"] == 2

    expired_id = create_diagnostics()
    with session_factory() as session:
        expired_command = session.get(DeviceCommand, UUID(expired_id))
        expired_command.expires_at = datetime.now(UTC) - timedelta(seconds=1)
        session.commit()
    polled_after_expiry = client.get("/api/v1/agent/commands", headers=agent_headers)
    assert all(item["id"] != expired_id for item in polled_after_expiry.json())
    history = client.get(
        f"/api/v1/devices/{device_id}/commands?limit=20", headers=owner_headers
    ).json()
    assert (
        next(item for item in history if item["id"] == expired_id)["status"]
        == "expired"
    )
