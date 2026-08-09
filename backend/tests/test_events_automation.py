import os
from dataclasses import replace
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import inspect, select, text
from sqlalchemy.orm import sessionmaker

from backend.app.config import load_settings
from backend.app.db import Base, get_engine, init_db
from backend.app.main import app
from backend.app.models import AutomationRun
from backend.app.services.events import emit_event, validate_notification_channels
from backend.app.services.telemetry_history import telemetry_alerts


def postgres_e2e_enabled() -> bool:
    return (
        bool(os.getenv("WRTMONITOR_DATABASE_URL"))
        and os.getenv("WRTMONITOR_SKIP_E2E", "0") != "1"
    )


def reset_database() -> None:
    init_db()
    tables = ", ".join(f'"{table.name}"' for table in Base.metadata.sorted_tables)
    factory = sessionmaker(bind=get_engine(), expire_on_commit=False)
    with factory() as db:
        db.execute(text(f"TRUNCATE TABLE {tables} RESTART IDENTITY CASCADE"))
        db.commit()


def owner_and_device(client: TestClient) -> tuple[dict[str, str], UUID, str]:
    setup = client.post(
        "/api/v1/setup/complete",
        json={
            "username": "events@example.com",
            "password": "events-test-password",
            "password_confirm": "events-test-password",
            "server_url": "http://127.0.0.1:8080",
        },
    )
    assert setup.status_code == 200
    login = client.post(
        "/api/v1/auth/login",
        json={"username": "events@example.com", "password": "events-test-password"},
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    device = client.post(
        "/api/v1/devices/provision",
        headers=headers,
        json={
            "name": "EventRouter",
            "hostname": "OpenWrt",
            "model": "CI",
            "firmware": "OpenWrt test",
        },
    )
    assert device.status_code == 200
    return headers, UUID(device.json()["device_id"]), device.json()["device_token"]


@pytest.mark.skipif(not postgres_e2e_enabled(), reason="PostgreSQL E2E required")
def test_event_deduplication_acknowledge_snooze_and_automation_dry_run():
    reset_database()
    client = TestClient(app)
    headers, device_id, _ = owner_and_device(client)

    notification = client.post(
        "/api/v1/operations/notification-rules",
        headers=headers,
        json={
            "name": "Warnings",
            "device_id": str(device_id),
            "event_types": ["client.online"],
            "severities": ["warning"],
            "channels": [{"type": "in_app"}],
        },
    )
    assert notification.status_code == 200

    automation = client.post(
        "/api/v1/operations/automation-rules",
        headers=headers,
        json={
            "name": "Refresh interfaces",
            "device_id": str(device_id),
            "trigger_type": "client.online",
            "action_command": "network.interfaces",
            "action_payload": {},
            "cooldown_seconds": 120,
            "max_runs_per_hour": 2,
            "dry_run": True,
        },
    )
    assert automation.status_code == 200

    factory = sessionmaker(bind=get_engine(), expire_on_commit=False)
    with factory() as db:
        first, created = emit_event(
            db,
            device_id=device_id,
            event_type="client.online",
            severity="warning",
            title="Client online",
            fingerprint=f"{device_id}:client:one",
            dedupe_seconds=300,
            config=load_settings(),
        )
        assert created
        repeated, created = emit_event(
            db,
            device_id=device_id,
            event_type="client.online",
            severity="warning",
            title="Client online",
            fingerprint=f"{device_id}:client:one",
            dedupe_seconds=300,
            config=load_settings(),
        )
        assert not created
        assert repeated.id == first.id
        assert repeated.occurrence_count == 2
        db.commit()
        event_id = first.id
        runs = db.scalars(select(AutomationRun)).all()
        assert len(runs) == 1
        assert runs[0].status == "dry_run"

    listed = client.get(
        f"/api/v1/operations/events?device_id={device_id}", headers=headers
    )
    assert listed.status_code == 200
    assert listed.json()[0]["occurrence_count"] == 2
    acknowledged = client.post(
        f"/api/v1/operations/events/{event_id}/acknowledge", headers=headers
    )
    assert acknowledged.status_code == 200
    assert acknowledged.json()["status"] == "acknowledged"
    snoozed = client.post(
        f"/api/v1/operations/events/{event_id}/snooze?minutes=60", headers=headers
    )
    assert snoozed.status_code == 200
    assert snoozed.json()["snoozed_until"]


@pytest.mark.skipif(not postgres_e2e_enabled(), reason="PostgreSQL E2E required")
def test_automation_rejects_command_cycles_and_unsafe_actions():
    reset_database()
    client = TestClient(app)
    headers, device_id, _ = owner_and_device(client)
    base = {
        "name": "Unsafe",
        "device_id": str(device_id),
        "action_payload": {},
        "cooldown_seconds": 60,
        "max_runs_per_hour": 2,
    }
    command_cycle = client.post(
        "/api/v1/operations/automation-rules",
        headers=headers,
        json={
            **base,
            "trigger_type": "command.completed",
            "action_command": "diagnostics.run",
        },
    )
    assert command_cycle.status_code == 422
    shell = client.post(
        "/api/v1/operations/automation-rules",
        headers=headers,
        json={
            **base,
            "trigger_type": "device.offline",
            "action_command": "agent.bash_script",
        },
    )
    assert shell.status_code == 422


def test_high_load_alert_uses_load_per_cpu_core():
    payload = {
        "system": {
            "cpu_count": 2,
            "load_1m": 3.2,
            "memory": {"total_kb": 1000, "available_kb": 800},
        },
        "network": {"interfaces": []},
    }
    alerts = telemetry_alerts(payload, 0)
    assert any(item["code"] == "load.high" for item in alerts)


def test_smtp_rule_keeps_credentials_out_of_database_payload():
    config = replace(
        load_settings(),
        smtp_host="smtp.example.com",
        smtp_username="owner",
        smtp_password="secret",
        smtp_from="wrtmonitor@example.com",
    )
    channels = validate_notification_channels(
        [
            {
                "type": "smtp",
                "to": "alerts@example.com",
                "host": "untrusted.example.com",
                "password": "must-not-be-stored",
            }
        ],
        config,
    )
    assert channels == [{"type": "smtp", "to": "alerts@example.com"}]


@pytest.mark.skipif(not postgres_e2e_enabled(), reason="PostgreSQL E2E required")
def test_automation_run_tracks_actual_agent_result_and_web_events_are_paginated():
    reset_database()
    client = TestClient(app)
    headers, device_id, device_token = owner_and_device(client)
    rule = client.post(
        "/api/v1/operations/automation-rules",
        headers=headers,
        json={
            "name": "Read interfaces",
            "device_id": str(device_id),
            "trigger_type": "client.online",
            "action_command": "network.interfaces",
            "action_payload": {},
            "cooldown_seconds": 60,
            "max_runs_per_hour": 2,
        },
    )
    assert rule.status_code == 200
    factory = sessionmaker(bind=get_engine(), expire_on_commit=False)
    with factory() as db:
        emit_event(
            db,
            device_id=device_id,
            event_type="client.online",
            title="Client online",
            fingerprint=f"{device_id}:client:automation",
        )
        for index in range(26):
            emit_event(
                db,
                device_id=device_id,
                event_type="test.page",
                title=f"Page event {index}",
                fingerprint=f"{device_id}:page:{index}",
                dedupe_seconds=0,
            )
        db.commit()
        run = db.scalar(select(AutomationRun))
        assert run and run.status == "queued" and run.command_id
        command_id = run.command_id

    claimed = client.get(
        "/api/v1/agent/commands?wait=0",
        headers={"Authorization": f"Bearer {device_token}"},
    )
    assert claimed.status_code == 200
    assert any(item["id"] == str(command_id) for item in claimed.json())
    completed = client.post(
        f"/api/v1/agent/commands/{command_id}/result",
        headers={"Authorization": f"Bearer {device_token}"},
        json={"status": "success", "result": {"interfaces": []}},
    )
    assert completed.status_code == 200
    runs = client.get("/api/v1/operations/automation-runs", headers=headers)
    assert runs.status_code == 200
    assert runs.json()[0]["status"] == "success"

    web_login = client.post(
        "/login",
        data={"username": "events@example.com", "password": "events-test-password"},
        follow_redirects=False,
    )
    assert web_login.status_code == 303
    first_page = client.get("/events?page=1")
    second_page = client.get("/events?page=2")
    assert first_page.status_code == second_page.status_code == 200
    assert "из 29" in first_page.text
    assert "2 / 2" in second_page.text


@pytest.mark.skipif(not postgres_e2e_enabled(), reason="PostgreSQL E2E required")
def test_events_schema_is_present():
    init_db()
    tables = set(inspect(get_engine()).get_table_names())
    assert {
        "event_records",
        "notification_rules",
        "automation_rules",
        "automation_runs",
    } <= tables
