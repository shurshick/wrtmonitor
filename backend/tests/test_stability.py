from datetime import UTC, datetime
from uuid import uuid4

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from pydantic import ValidationError

from backend.app.main import app
from backend.app.api import agent as agent_api
from backend.app.api import health as health_api
from backend.app.config import load_settings
from backend.app.models import Device
from backend.app.schemas import TelemetryRequest
from backend.app.security import hash_token
from backend.app.services.commands import create_device_command


def test_unknown_telemetry_contract_is_rejected() -> None:
    with pytest.raises(ValidationError):
        TelemetryRequest(
            device_id=uuid4(),
            telemetry={"schema_version": 999},
        )


def test_legacy_telemetry_contract_remains_supported() -> None:
    payload = TelemetryRequest(device_id=uuid4(), telemetry={"system": {}})
    assert payload.telemetry == {"system": {}}


def test_idempotency_key_returns_the_existing_command() -> None:
    class Scalars:
        def __init__(self, item):
            self.item = item

        def first(self):
            return self.item

    class Session:
        existing = None

        def scalars(self, _statement):
            return Scalars(self.existing)

        def add(self, item):
            self.existing = item

    db = Session()
    device_id = uuid4()
    key = "android-command-123"
    first = create_device_command(
        db,
        device_id=device_id,
        command_type="router.reboot",
        payload={},
        created_by=uuid4(),
        source="test",
        idempotency_key=key,
    )
    second = create_device_command(
        db,
        device_id=device_id,
        command_type="router.reboot",
        payload={},
        created_by=uuid4(),
        source="test",
        idempotency_key=key,
    )
    assert second is first

    with pytest.raises(HTTPException) as exc:
        create_device_command(
            db,
            device_id=device_id,
            command_type="network.restart",
            payload={},
            created_by=uuid4(),
            source="test",
            idempotency_key=key,
        )
    assert exc.value.status_code == 409


def test_liveness_contracts_and_metrics_are_exposed() -> None:
    client = TestClient(app)
    assert client.get("/live").json() == {"status": "ok"}
    contracts = client.get("/api/v1/meta/contracts")
    assert contracts.status_code == 200
    assert contracts.json()["command_contract_version"] == 1
    assert contracts.json()["telemetry_schema_current"] == 2
    assert client.get("/metrics").status_code == 404
    config = load_settings()
    app.dependency_overrides[health_api.settings] = lambda: config.__class__(
        **{**config.__dict__, "enable_metrics": True}
    )
    try:
        metrics = client.get("/metrics")
        assert metrics.status_code == 200
        assert "wrtmonitor_http_requests_total" in metrics.text
    finally:
        app.dependency_overrides.clear()


def test_unmatched_routes_do_not_create_unbounded_metric_labels() -> None:
    client = TestClient(app)
    client.get('/missing-"metric-label')
    config = load_settings()
    app.dependency_overrides[health_api.settings] = lambda: config.__class__(
        **{**config.__dict__, "enable_metrics": True}
    )
    try:
        metrics = client.get("/metrics").text
    finally:
        app.dependency_overrides.clear()
    assert '/missing-"metric-label' not in metrics
    assert 'route="<unmatched>"' in metrics


def test_agent_token_rotation_keeps_a_short_grace_period(monkeypatch) -> None:
    now = datetime.now(UTC)
    device = Device(
        id=uuid4(),
        token_hash=hash_token("old-token"),
        status="online",
        created_at=now,
        updated_at=now,
    )

    class Session:
        committed = False

        def commit(self) -> None:
            self.committed = True

    db = Session()
    monkeypatch.setattr(
        agent_api, "device_from_token", lambda _auth, _db, **_kwargs: device
    )
    monkeypatch.setattr(agent_api, "audit", lambda *_args, **_kwargs: None)

    response = agent_api.rotate_device_token("Bearer old-token", db)

    assert response["grace_seconds"] == 600
    assert response["device_token"] != "old-token"
    assert len(response["rollback_token"]) >= 32
    assert device.token_hash == hash_token(response["device_token"])
    assert device.previous_token_hash == hash_token("old-token")
    assert device.token_rollback_hash == hash_token(response["rollback_token"])
    assert device.previous_token_expires_at is not None
    assert device.previous_token_expires_at > now
    assert db.committed


def test_agent_token_rotation_can_be_rolled_back(monkeypatch) -> None:
    now = datetime.now(UTC)
    old_hash = hash_token("old-token")
    device = Device(
        id=uuid4(),
        token_hash=hash_token("new-token"),
        previous_token_hash=old_hash,
        previous_token_expires_at=now,
        token_rollback_hash=hash_token("rollback-token-value-with-32-characters"),
        status="online",
        created_at=now,
        updated_at=now,
    )

    class Scalars:
        def first(self):
            return device

    class Session:
        committed = False

        def scalars(self, _statement):
            return Scalars()

        def commit(self) -> None:
            self.committed = True

    db = Session()
    monkeypatch.setattr(agent_api, "audit", lambda *_args, **_kwargs: None)

    response = agent_api.rollback_device_token(
        agent_api.AgentTokenRollbackRequest(
            rollback_token="rollback-token-value-with-32-characters"
        ),
        "Bearer old-token",
        db,
    )

    assert response == {"status": "rolled_back"}
    assert device.token_hash == old_hash
    assert device.previous_token_hash is None
    assert device.previous_token_expires_at is None
    assert device.token_rollback_hash is None
    assert db.committed


def test_agent_token_rotation_confirmation_closes_grace_period(monkeypatch) -> None:
    now = datetime.now(UTC)
    device = Device(
        id=uuid4(),
        token_hash=hash_token("new-token"),
        previous_token_hash=hash_token("old-token"),
        previous_token_expires_at=now,
        token_rollback_hash=hash_token("rollback-token-value-with-32-characters"),
        status="online",
        created_at=now,
        updated_at=now,
    )

    class Session:
        committed = False

        def commit(self) -> None:
            self.committed = True

    db = Session()
    monkeypatch.setattr(
        agent_api, "device_from_token", lambda _auth, _db, **_kwargs: device
    )
    monkeypatch.setattr(agent_api, "audit", lambda *_args, **_kwargs: None)

    response = agent_api.confirm_device_token("Bearer new-token", db)

    assert response == {"status": "confirmed"}
    assert device.previous_token_hash is None
    assert device.previous_token_expires_at is None
    assert device.token_rollback_hash is None
    assert db.committed
