import json
import os
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select
from sqlalchemy.orm import sessionmaker

from backend.app.config import load_settings
from backend.app.db import get_engine, init_db
from backend.app.main import app
from backend.app.models import (
    AppSetting,
    AuditLog,
    MobilePairingAttempt,
    MobilePairingToken,
    User,
    UserSession,
)
from backend.app.security import hash_token
from backend.app.services.mobile_pairing import PAIRING_TYPE, PAIRING_VERSION


def postgres_e2e_enabled() -> bool:
    return (
        bool(os.getenv("WRTMONITOR_DATABASE_URL"))
        and os.getenv("WRTMONITOR_SKIP_E2E", "0") != "1"
    )


def clear_database() -> None:
    init_db()
    factory = sessionmaker(bind=get_engine(), autoflush=False, expire_on_commit=False)
    with factory() as db:
        for model in (MobilePairingAttempt, AuditLog, UserSession, AppSetting, User):
            db.execute(delete(model))
        db.commit()


def setup_owner(
    client: TestClient, server_url: str = "https://monitor.example.ru"
) -> dict:
    response = client.post(
        "/api/v1/setup/complete",
        json={
            "username": "pairing@example.com",
            "password": "pairing-test-password",
            "password_confirm": "pairing-test-password",
            "server_url": server_url,
        },
    )
    assert response.status_code == 200
    login = client.post(
        "/api/v1/auth/login",
        json={"username": "pairing@example.com", "password": "pairing-test-password"},
    )
    assert login.status_code == 200
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def test_mobile_pairing_lifecycle_and_secret_storage():
    if not postgres_e2e_enabled():
        pytest.skip("PostgreSQL E2E test requires WRTMONITOR_DATABASE_URL")
    clear_database()
    client = TestClient(app)
    headers = setup_owner(client)

    assert client.post("/api/v1/mobile-pairing/tokens").status_code == 401
    created = client.post("/api/v1/mobile-pairing/tokens", headers=headers)
    assert created.status_code == 200
    body = created.json()
    assert body["status"] == "active"
    assert body["server_url"] == "https://monitor.example.ru"
    expires = datetime.fromisoformat(body["expires_at"])
    created_at = datetime.fromisoformat(body["created_at"])
    assert expires - created_at == timedelta(minutes=10)

    setup_payload = json.loads(body["setup_payload"])
    assert setup_payload == {
        "type": PAIRING_TYPE,
        "version": PAIRING_VERSION,
        "server_url": "https://monitor.example.ru",
        "pairing_token": setup_payload["pairing_token"],
    }
    raw_token = setup_payload["pairing_token"]

    factory = sessionmaker(bind=get_engine(), autoflush=False, expire_on_commit=False)
    with factory() as db:
        item = db.get(MobilePairingToken, UUID(body["id"]))
        assert item is not None
        assert item.token_hash == hash_token(raw_token)
        assert raw_token not in item.token_hash
        serialized_audit = json.dumps(
            [entry.details for entry in db.scalars(select(AuditLog)).all()],
            default=str,
        )
        assert raw_token not in serialized_audit

    exchange = client.post(
        "/api/v1/mobile-pairing/exchange",
        json={"pairing_token": raw_token, "client_name": "Android test"},
    )
    assert exchange.status_code == 200
    assert exchange.json()["access_token"]
    assert exchange.json()["refresh_token"]
    assert exchange.json()["server_url"] == "https://monitor.example.ru"
    assert exchange.json()["owner"]["username"] == "pairing@example.com"

    repeated = client.post(
        "/api/v1/mobile-pairing/exchange",
        json={"pairing_token": raw_token, "client_name": "Replay"},
    )
    assert repeated.status_code == 410
    assert repeated.json()["detail"]["code"] == "pairing_used"
    state = client.get(f"/api/v1/mobile-pairing/tokens/{body['id']}", headers=headers)
    assert state.json()["status"] == "used"

    sessions = client.get(
        "/api/v1/auth/sessions?client_type=mobile_pairing", headers=headers
    )
    assert sessions.status_code == 200
    assert len(sessions.json()) == 1
    assert sessions.json()[0]["client_type"] == "mobile_pairing"
    session_id = sessions.json()[0]["id"]
    revoked = client.delete(f"/api/v1/auth/sessions/{session_id}", headers=headers)
    assert revoked.status_code == 200
    active_sessions = client.get(
        "/api/v1/auth/sessions?client_type=mobile_pairing&active_only=true",
        headers=headers,
    )
    assert active_sessions.status_code == 200
    assert active_sessions.json() == []
    refresh = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": exchange.json()["refresh_token"]},
    )
    assert refresh.status_code == 401
    with factory() as db:
        actions = {entry.action for entry in db.scalars(select(AuditLog)).all()}
        assert {
            "mobile_pairing.token.created",
            "mobile_pairing.token.used",
            "mobile_pairing.token.used_attempt",
            "mobile_pairing.session.created",
            "mobile_pairing.session.revoked",
        } <= actions
        serialized_audit = json.dumps(
            [entry.details for entry in db.scalars(select(AuditLog)).all()],
            default=str,
        )
        assert raw_token not in serialized_audit
        assert exchange.json()["access_token"] not in serialized_audit
        assert exchange.json()["refresh_token"] not in serialized_audit


def test_mobile_pairing_rejects_expired_revoked_invalid_and_rate_limited_tokens():
    if not postgres_e2e_enabled():
        pytest.skip("PostgreSQL E2E test requires WRTMONITOR_DATABASE_URL")
    clear_database()
    client = TestClient(app)
    headers = setup_owner(client)
    factory = sessionmaker(bind=get_engine(), autoflush=False, expire_on_commit=False)

    expired = client.post("/api/v1/mobile-pairing/tokens", headers=headers).json()
    expired_token = json.loads(expired["setup_payload"])["pairing_token"]
    with factory() as db:
        item = db.get(MobilePairingToken, UUID(expired["id"]))
        item.expires_at = datetime.now(UTC) - timedelta(seconds=1)
        db.commit()
    response = client.post(
        "/api/v1/mobile-pairing/exchange",
        json={"pairing_token": expired_token, "client_name": "Expired"},
    )
    assert response.status_code == 410
    assert response.json()["detail"]["code"] == "pairing_expired"

    active = client.post("/api/v1/mobile-pairing/tokens", headers=headers).json()
    revoked_token = json.loads(active["setup_payload"])["pairing_token"]
    revoked = client.delete(
        f"/api/v1/mobile-pairing/tokens/{active['id']}", headers=headers
    )
    assert revoked.status_code == 200
    response = client.post(
        "/api/v1/mobile-pairing/exchange",
        json={"pairing_token": revoked_token, "client_name": "Revoked"},
    )
    assert response.status_code == 410
    assert response.json()["detail"]["code"] == "pairing_revoked"

    invalid_token = "x" * 43
    for _ in range(5):
        response = client.post(
            "/api/v1/mobile-pairing/exchange",
            json={"pairing_token": invalid_token, "client_name": "Invalid"},
        )
        assert response.status_code == 401
    limited = client.post(
        "/api/v1/mobile-pairing/exchange",
        json={"pairing_token": invalid_token, "client_name": "Limited"},
    )
    assert limited.status_code == 429
    assert limited.json()["detail"]["code"] == "pairing_rate_limited"
    with factory() as db:
        actions = {entry.action for entry in db.scalars(select(AuditLog)).all()}
        assert "mobile_pairing.token.expired_attempt" in actions
        assert "mobile_pairing.token.revoked" in actions
        assert "mobile_pairing.token.revoked_attempt" in actions
        assert "mobile_pairing.invalid_attempt" in actions
        assert "mobile_pairing.rate_limited" in actions


def test_pairing_public_url_policy_rejects_http_in_secure_mode():
    config = load_settings()
    assert config.allow_insecure_local is True
    from backend.app.config import validate_server_url

    with pytest.raises(ValueError):
        validate_server_url("http://monitor.example.ru", allow_insecure_local=False)
    with pytest.raises(ValueError):
        validate_server_url("http://monitor.example.ru", allow_insecure_local=True)
    with pytest.raises(ValueError):
        validate_server_url(
            "https://monitor.example.ru/pairing", allow_insecure_local=False
        )
    assert (
        validate_server_url("http://192.168.1.10:8088/", allow_insecure_local=True)
        == "http://192.168.1.10:8088"
    )
