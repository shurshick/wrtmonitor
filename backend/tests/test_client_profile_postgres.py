from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.db import get_engine, init_db
from backend.app.models import (
    ClientProfile,
    Device,
    DeviceCommand,
    DeviceTelemetry,
    NetworkClient,
    User,
)
from backend.app.services.client_profile_commands import queue_profile_commands
from backend.tests.test_api import postgres_e2e_enabled


@pytest.mark.parametrize("removing", [False, True])
def test_profile_commands_are_persisted_with_client_changes(removing):
    if not postgres_e2e_enabled():
        pytest.skip("PostgreSQL E2E test requires WRTMONITOR_DATABASE_URL")
    init_db()
    now = datetime.now(UTC)
    with Session(get_engine(), autoflush=False) as db:
        user = User(
            id=uuid4(),
            username=f"profile-{uuid4()}",
            password_hash="unused",
            created_at=now,
            updated_at=now,
        )
        device = Device(
            id=uuid4(),
            name="Profile regression",
            token_hash=str(uuid4()),
            created_at=now,
            updated_at=now,
        )
        db.add_all([user, device])
        db.flush()
        profile = ClientProfile(
            id=uuid4(),
            device_id=device.id,
            name="Shared",
            policy={"blocked": True},
            created_at=now,
            updated_at=now,
        )
        db.add(profile)
        db.flush()
        clients = [
            NetworkClient(
                id=uuid4(),
                device_id=device.id,
                profile_id=profile.id,
                mac="02:00:00:00:00:01",
                policy={},
                first_seen_at=now,
                last_seen_at=now,
                updated_at=now,
            ),
            NetworkClient(
                id=uuid4(),
                device_id=device.id,
                profile_id=profile.id,
                mac="02:00:00:00:00:02",
                policy={
                    "blocked": False,
                    "qos": {"download_kbps": 5000, "upload_kbps": 1000},
                },
                first_seen_at=now,
                last_seen_at=now,
                updated_at=now,
            ),
        ]
        db.add_all(clients)
        db.add(
            DeviceTelemetry(
                id=uuid4(),
                device_id=device.id,
                created_at=now,
                payload={
                    "agent": {
                        "capabilities": {
                            "clients.policy": True,
                            "clients.shaping": True,
                            "config.transaction": True,
                        }
                    }
                },
            )
        )
        db.flush()
        ids = queue_profile_commands(
            db, profile, created_by=user.id, source="api", removing=removing
        )
        if removing:
            db.delete(profile)
        db.flush()
        commands = db.scalars(
            select(DeviceCommand).where(DeviceCommand.device_id == device.id)
        ).all()
        assert {str(command.id) for command in commands} == set(ids)
        assert len(commands) == 2
        by_mac = {command.payload["mac"]: command.payload for command in commands}
        assert by_mac[clients[0].mac]["blocked"] is (not removing)
        assert by_mac[clients[1].mac]["blocked"] is False
        assert by_mac[clients[1].mac]["qos"]["download_kbps"] == 5000
        for client in clients:
            db.refresh(client)
            assert client.profile_id == (None if removing else profile.id)
        # Leave no test records in the shared CI database.
        db.rollback()
