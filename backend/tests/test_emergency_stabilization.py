from types import SimpleNamespace
from uuid import uuid4
from contextlib import contextmanager

import pytest
from fastapi.testclient import TestClient

import backend.app.api.ssh as ssh_api
from backend.app.db import get_db
from backend.app.main import app
from backend.tests.test_api import clear_database, postgres_e2e_enabled


def test_terminal_websocket_requires_same_origin():
    matching = SimpleNamespace(
        headers={"origin": "https://router.example", "host": "router.example"}
    )
    foreign = SimpleNamespace(
        headers={"origin": "https://attacker.example", "host": "router.example"}
    )
    missing = SimpleNamespace(headers={"host": "router.example"})

    assert ssh_api._websocket_is_same_origin(matching) is True
    assert ssh_api._websocket_is_same_origin(foreign) is False
    assert ssh_api._websocket_is_same_origin(missing) is False


def test_terminal_upload_rejects_token_for_another_device(monkeypatch):
    authenticated_device_id = uuid4()
    target_device_id = uuid4()
    session_id = uuid4()

    def fake_db():
        yield object()

    monkeypatch.setattr(
        ssh_api,
        "device_from_token",
        lambda authorization, db: SimpleNamespace(id=authenticated_device_id),
    )
    monkeypatch.setattr(
        ssh_api,
        "get_terminal_session",
        lambda db, requested_session_id: SimpleNamespace(device_id=target_device_id),
    )
    app.dependency_overrides[get_db] = fake_db
    try:
        response = TestClient(app).put(
            f"/api/v1/agent/terminal/sessions/{session_id}/up",
            headers={"Authorization": "Bearer router-token"},
            content=b"hostname\n",
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403
    assert response.json()["detail"] == "Device token does not match terminal session"


def test_terminal_upload_accepts_matching_device_token(monkeypatch):
    device_id = uuid4()
    session_id = uuid4()

    def fake_db():
        yield object()

    monkeypatch.setattr(
        ssh_api,
        "device_from_token",
        lambda authorization, db: SimpleNamespace(id=device_id),
    )
    monkeypatch.setattr(
        ssh_api,
        "get_terminal_session",
        lambda db, requested_session_id: SimpleNamespace(device_id=device_id),
    )

    @contextmanager
    def fake_broker_session():
        yield SimpleNamespace(commit=lambda: None)

    stored = []
    monkeypatch.setattr(ssh_api, "broker_session", fake_broker_session)
    monkeypatch.setattr(ssh_api, "set_terminal_status", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        ssh_api,
        "append_terminal_frame",
        lambda *args, **kwargs: stored.append(kwargs["payload"]),
    )
    monkeypatch.setattr(ssh_api, "trim_terminal_frames", lambda *args, **kwargs: 0)
    app.dependency_overrides[get_db] = fake_db
    try:
        response = TestClient(app).put(
            f"/api/v1/agent/terminal/sessions/{session_id}/up",
            headers={"Authorization": "Bearer router-token"},
            content=b"hostname\n",
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "bytes": 9}
    assert b"".join(stored) == b"hostname\n"


def test_fleet_group_creation_and_capability_filtering_e2e():
    if not postgres_e2e_enabled():
        pytest.skip("PostgreSQL E2E test requires WRTMONITOR_DATABASE_URL")

    clear_database()
    with TestClient(app) as client:
        setup = client.post(
            "/api/v1/setup/complete",
            json={
                "username": "fleet@example.com",
                "password": "secret-password",
                "password_confirm": "secret-password",
                "server_url": "http://127.0.0.1:8080",
            },
        )
        assert setup.status_code == 200
        login = client.post(
            "/api/v1/auth/login",
            json={"username": "fleet@example.com", "password": "secret-password"},
        )
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

        routers = []
        for index in range(2):
            provision = client.post(
                "/api/v1/devices/provision",
                headers=headers,
                json={
                    "name": f"Router-{index}",
                    "hostname": f"openwrt-{index}",
                    "model": "CI",
                    "firmware": "OpenWrt",
                },
            )
            assert provision.status_code == 200
            routers.append(provision.json())

        group = client.post(
            "/api/v1/fleet/groups",
            headers=headers,
            json={"name": "Lab", "description": "Integration routers"},
        )
        assert group.status_code == 200
        assert group.json()["id"]
        assert group.json()["created_at"]
        group_id = group.json()["id"]

        assignment = client.post(
            f"/api/v1/fleet/groups/{group_id}/devices",
            headers=headers,
            json={"device_ids": [router["device_id"] for router in routers]},
        )
        assert assignment.json() == {"assigned": 2}

        for index, router in enumerate(routers):
            telemetry = client.post(
                "/api/v1/agent/telemetry",
                headers={"Authorization": f"Bearer {router['device_token']}"},
                json={
                    "device_id": router["device_id"],
                    "telemetry": {
                        "schema_version": 2,
                        "agent": {
                            "capabilities": {"diagnostics.check_server": index == 0}
                        },
                    },
                },
            )
            assert telemetry.status_code == 200

        dispatch = client.post(
            f"/api/v1/fleet/groups/{group_id}/commands",
            headers=headers,
            json={"command_type": "diagnostics.run", "payload": {}},
        )
        assert dispatch.status_code == 200
        result = dispatch.json()
        assert set(result["command_ids"]) == {routers[0]["device_id"]}
        assert set(result["skipped"]) == {routers[1]["device_id"]}
        assert "does not support capability" in next(iter(result["skipped"].values()))
