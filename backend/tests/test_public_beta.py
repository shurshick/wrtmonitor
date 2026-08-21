import io
import os
import zipfile
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker

from backend.app.db import Base, get_engine, init_db
from backend.app.main import app
from backend.app.models import FeedbackRecord, User


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


@pytest.mark.skipif(not postgres_e2e_enabled(), reason="PostgreSQL E2E required")
def test_feedback_and_safe_diagnostic_report() -> None:
    reset_database()
    client = TestClient(app)
    setup = client.post(
        "/api/v1/setup/complete",
        json={
            "username": "beta@example.com",
            "password": "public-beta-password",
            "password_confirm": "public-beta-password",
            "server_url": "http://127.0.0.1:8080",
        },
    )
    assert setup.status_code == 200
    login = client.post(
        "/api/v1/auth/login",
        json={"username": "beta@example.com", "password": "public-beta-password"},
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    provision = client.post(
        "/api/v1/devices/provision",
        headers=headers,
        json={
            "name": "BetaRouter",
            "hostname": "OpenWrt",
            "model": "Test",
            "firmware": "OpenWrt test",
        },
    )
    assert provision.status_code == 200
    device_id = provision.json()["device_id"]

    feedback = client.post(
        "/api/v1/operations/feedback",
        headers=headers,
        json={
            "category": "bug",
            "message": "Router overview did not refresh after reconnect.",
            "device_id": device_id,
            "source": "android",
            "app_version": "0.51.0",
            "client_context": {
                "platform": "android",
                "screen": "overview",
                "password": "must-not-be-stored",
            },
        },
    )
    assert feedback.status_code == 201
    duplicate = client.post(
        "/api/v1/operations/feedback",
        headers=headers,
        json={
            "category": "bug",
            "message": "Router overview did not refresh after reconnect.",
            "device_id": device_id,
            "source": "android",
            "app_version": "0.51.0",
        },
    )
    assert duplicate.status_code == 201
    assert duplicate.json()["id"] == feedback.json()["id"]
    assert duplicate.json()["duplicate"] is True

    factory = sessionmaker(bind=get_engine(), expire_on_commit=False)
    now = datetime.now(UTC)
    with factory() as db:
        other_user = User(
            id=uuid4(),
            username="other@example.com",
            password_hash="unused",
            role="owner",
            disabled=False,
            created_at=now,
            updated_at=now,
        )
        db.add(other_user)
        db.add(
            FeedbackRecord(
                id=uuid4(),
                user_id=other_user.id,
                device_id=None,
                source="api",
                category="other",
                message="This feedback belongs to another administrator.",
                app_version="0.51.0",
                client_context={},
                status="new",
                created_at=now,
            )
        )
        db.commit()

    listed = client.get("/api/v1/operations/feedback", headers=headers)
    assert listed.status_code == 200
    assert len(listed.json()) == 1
    assert listed.json()[0]["message"].startswith("Router overview")

    report = client.get(
        f"/api/v1/operations/diagnostics/report/{device_id}", headers=headers
    )
    assert report.status_code == 200
    assert report.json()["schema"] == "wrtmonitor.support-report.v1"
    assert report.json()["device"]["name"] == "BetaRouter"
    serialized = report.text.lower()
    assert "device_token" not in serialized
    assert "password" not in serialized

    archive = client.get("/api/v1/operations/diagnostics/archive", headers=headers)
    assert archive.status_code == 200
    with zipfile.ZipFile(io.BytesIO(archive.content)) as content:
        assert "routers.json" in content.namelist()
        assert "BetaRouter" in content.read("routers.json").decode("utf-8")

    for index in range(4):
        accepted = client.post(
            "/api/v1/operations/feedback",
            headers=headers,
            json={
                "category": "usability",
                "message": f"Distinct usability report number {index} for rate testing.",
                "source": "android",
            },
        )
        assert accepted.status_code == 201
    limited = client.post(
        "/api/v1/operations/feedback",
        headers=headers,
        json={
            "category": "other",
            "message": "This sixth report must be rejected by the feedback limiter.",
            "source": "android",
        },
    )
    assert limited.status_code == 429
    assert limited.json()["detail"]["code"] == "feedback_rate_limited"
