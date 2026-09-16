from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import ClientProfile, NetworkClient
from .client_registry import validate_client_policy
from .command_store import create_device_command, validate_command_request
from .devices import device_supports
from .wifi_access_profiles import assigned_wifi_interfaces, wifi_access_profile_payload


def queue_profile_commands(
    db: Session,
    profile: ClientProfile,
    *,
    created_by: UUID,
    source: str,
    removing: bool = False,
) -> list[str]:
    clients = db.scalars(
        select(NetworkClient).where(
            NetworkClient.device_id == profile.device_id,
            NetworkClient.profile_id == profile.id,
        )
    ).all()
    planned = [
        (
            "wifi.set_access_profile",
            wifi_access_profile_payload(iface, None if removing else profile),
        )
        for iface in assigned_wifi_interfaces(db, profile.device_id, profile.id)
    ]
    for client in clients:
        policy = dict({} if removing else profile.policy or {})
        policy.update(client.policy or {})
        policy = validate_client_policy(policy)
        qos = policy["qos"]
        if (qos["download_kbps"] > 0 or qos["upload_kbps"] > 0) and not device_supports(
            db, profile.device_id, "clients.shaping"
        ):
            raise HTTPException(
                status_code=409,
                detail="Client speed limits require clients.shaping capability",
            )
        planned.append(("client.set_policy", {"mac": client.mac, **policy}))

    # Validate every target before queueing any changes in the caller's transaction.
    normalized = [
        (
            command_type,
            validate_command_request(
                command_type=command_type,
                payload=payload,
                confirmed=True,
                device_supports=lambda capability: device_supports(
                    db, profile.device_id, capability
                ),
            ),
        )
        for command_type, payload in planned
    ]
    command_ids = []
    for command_type, payload in normalized:
        command = create_device_command(
            db,
            device_id=profile.device_id,
            command_type=command_type,
            payload=payload,
            created_by=created_by,
            source=source,
        )
        command_ids.append(str(command.id))
    if removing:
        for client in clients:
            client.profile_id = None
            client.updated_at = datetime.now(UTC)
    return command_ids
