from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

from backend.app.models import ClientProfile
from backend.app.services import wifi_access_profiles


def test_profile_is_expanded_to_router_command_payload():
    profile = ClientProfile(
        id=uuid4(),
        device_id=uuid4(),
        name="Guests",
        policy={
            "blocked": False,
            "schedule": {
                "enabled": True,
                "weekdays": ["sat", "sun"],
                "start": "09:00",
                "stop": "23:00",
            },
            "qos": {"download_kbps": 20000, "upload_kbps": 5000},
        },
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    payload = wifi_access_profiles.wifi_access_profile_payload("guest", profile)

    assert payload["profile_id"] == str(profile.id)
    assert payload["schedule"]["weekdays"] == ["sat", "sun"]
    assert payload["qos"] == {"download_kbps": 20000, "upload_kbps": 5000}


def test_assigned_interfaces_are_read_from_observed_telemetry(monkeypatch):
    device_id = uuid4()
    profile_id = uuid4()
    telemetry = SimpleNamespace(
        payload={
            "wifi": {
                "radios": [
                    {
                        "id": "radio0",
                        "interfaces": [
                            {
                                "id": "main",
                                "mode": "ap",
                                "network": "lan",
                                "access_profile": {"profile_id": str(profile_id)},
                            },
                            {
                                "id": "guest",
                                "mode": "ap",
                                "network": "guest",
                                "access_profile": {"profile_id": str(profile_id)},
                            },
                        ],
                    }
                ]
            }
        }
    )
    monkeypatch.setattr(
        wifi_access_profiles, "latest_device_telemetry", lambda db, value: telemetry
    )

    assert wifi_access_profiles.assigned_wifi_interfaces(
        object(), device_id, profile_id
    ) == ["guest", "main"]


def test_profile_removal_payload_has_no_stale_snapshot():
    assert wifi_access_profiles.wifi_access_profile_payload("guest", None) == {
        "iface": "guest",
        "enabled": False,
    }
