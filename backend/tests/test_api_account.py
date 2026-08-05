import pytest
from unittest.mock import MagicMock
from uuid import uuid4
from datetime import datetime, timezone
from fastapi.testclient import TestClient

from app.main import app
from app.models import AuditLog, UserSession, User
from app.db import get_db
from app.services.auth import current_user


@pytest.fixture(name="db_session")
def db_session_fixture():
    return MagicMock()


@pytest.fixture
def test_user():
    user = User(id=uuid4(), username="admin", password_hash="fake", role="admin")
    return user


@pytest.fixture(name="client")
def client_fixture(db_session, test_user):
    def get_db_override():
        yield db_session

    def get_user_override():
        return test_user

    app.dependency_overrides[get_db] = get_db_override
    app.dependency_overrides[current_user] = get_user_override

    yield TestClient(app)

    app.dependency_overrides.clear()


def test_get_audit_logs(client, test_user, db_session):
    log = AuditLog(
        id=uuid4(),
        user_id=test_user.id,
        action="test_action",
        created_at=datetime.now(timezone.utc),
    )

    mock_result = MagicMock()
    mock_result.__iter__.return_value = [log]
    db_session.scalars.return_value = mock_result

    resp = client.get("/api/v1/account/audit")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    assert data[0]["action"] == "test_action"


def test_get_sessions(client, test_user, db_session):
    sess = UserSession(
        id=uuid4(),
        user_id=test_user.id,
        client_type="web",
        refresh_token_hash="hash",
        created_at=datetime.now(timezone.utc),
        expires_at=datetime.now(timezone.utc),
    )

    mock_result = MagicMock()
    mock_result.__iter__.return_value = [sess]
    db_session.scalars.return_value = mock_result

    resp = client.get("/api/v1/account/sessions")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    assert data[0]["client_type"] == "web"


def test_revoke_session(client, test_user, db_session):
    session_id = uuid4()
    sess = UserSession(
        id=session_id,
        user_id=test_user.id,
        client_type="web",
        refresh_token_hash="hash",
        created_at=datetime.now(timezone.utc),
        expires_at=datetime.now(timezone.utc),
    )
    db_session.get.return_value = sess

    resp = client.post(f"/api/v1/account/sessions/{session_id}/revoke")
    assert resp.status_code == 200
    assert db_session.commit.called
