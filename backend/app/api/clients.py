from datetime import UTC, datetime
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import (
    ClientActivityEvent,
    ClientProfile,
    ClientTrafficSample,
    NetworkClient,
    User,
)
from ..schemas import ClientProfileRequest, ClientUpdateRequest
from ..services.audit import audit
from ..services.auth import current_user
from ..services.client_registry import (
    client_response,
    effective_policy,
    infer_device_type,
    validate_device_type,
    validate_client_policy,
)
from ..services.commands import create_device_command, validate_command_request
from ..services.devices import (
    device_supports,
    get_user_device_or_404,
    latest_device_telemetry,
)
from ..services.telemetry import normalize_wifi_summary


router = APIRouter(prefix="/api/v1/devices")


def _client_connection_details(payload: dict) -> dict[str, dict]:
    clients = payload.get("clients") or {}
    neighbours = clients.get("neighbours") or []
    details: dict[str, dict] = {}
    for neighbour in neighbours:
        if not isinstance(neighbour, dict):
            continue
        mac = str(neighbour.get("mac") or "").lower()
        if not mac:
            continue
        item = details.setdefault(mac, {"ipv4": "", "ipv6": []})
        address = str(neighbour.get("ip") or "")
        if "." in address:
            item["ipv4"] = address
        elif ":" in address and address not in item["ipv6"]:
            item["ipv6"].append(address)
        interface = str(neighbour.get("interface") or "")
        if interface:
            item["interface"] = interface

    for station in normalize_wifi_summary(payload).get("stations") or []:
        item = details.setdefault(station["mac"], {"ipv4": "", "ipv6": []})
        item.update(
            {
                "connection_type": "wifi",
                "connection_name": station.get("ssid") or "",
                "wifi_ssid": station.get("ssid") or "",
                "wifi_band": station.get("band") or "",
                "wifi_interface": station.get("interface") or "",
                "signal_dbm": station.get("signal"),
                "rx_bitrate": station.get("rx_bitrate"),
                "tx_bitrate": station.get("tx_bitrate"),
            }
        )
    return details


def get_client(db: Session, device_id: UUID, client_id: UUID) -> NetworkClient:
    client = db.get(NetworkClient, client_id)
    if not client or client.device_id != device_id:
        raise HTTPException(status_code=404, detail="Client not found")
    return client


def _update_client_record(
    db: Session,
    device_id: UUID,
    client: NetworkClient,
    payload: ClientUpdateRequest,
) -> None:
    if "profile_id" in payload.model_fields_set:
        if payload.profile_id is None:
            client.profile_id = None
        else:
            profile = db.get(ClientProfile, payload.profile_id)
            if not profile or profile.device_id != device_id:
                raise HTTPException(
                    status_code=422, detail="Profile does not belong to this router"
                )
            client.profile_id = profile.id
    if payload.display_name is not None:
        client.display_name = payload.display_name.strip() or None
    if payload.device_type is not None:
        selected_type = validate_device_type(payload.device_type)
        if selected_type == "unknown":
            client.device_type = infer_device_type(
                client.display_name, client.hostname, client.vendor
            )
            client.device_type_source = "automatic"
        else:
            client.device_type = selected_type
            client.device_type_source = "user"
    if payload.policy is not None:
        client.policy = (
            {}
            if client.profile_id is not None and not payload.policy
            else validate_client_policy(payload.policy)
        )
    client.updated_at = datetime.now(UTC)


def _queue_client_policy(
    db: Session,
    device_id: UUID,
    client: NetworkClient,
    user: User,
    source: str,
):
    policy = effective_policy(db, client)
    qos = policy.get("qos") or {}
    if (
        int(qos.get("download_kbps") or 0) > 0 or int(qos.get("upload_kbps") or 0) > 0
    ) and not device_supports(db, device_id, "clients.shaping"):
        raise HTTPException(
            status_code=409,
            detail="Agent update or tc-full is required for client speed limits",
        )
    normalized = validate_command_request(
        command_type="client.set_policy",
        payload={"mac": client.mac, **policy},
        confirmed=True,
        device_supports=lambda capability: device_supports(db, device_id, capability),
    )
    return create_device_command(
        db,
        device_id=device_id,
        command_type="client.set_policy",
        payload=normalized,
        created_by=user.id,
        source=source,
    )


def _enrich_client(
    item: dict,
    telemetry_payload: dict,
    connection_by_mac: dict[str, dict] | None = None,
) -> dict:
    mac_key = str(item.get("mac") or "").lower()
    dhcp = (
        telemetry_payload.get("dhcp")
        or (telemetry_payload.get("clients") or {}).get("dhcp")
        or {}
    )
    lease_ipv4_by_mac = {
        str(lease.get("mac") or "").lower(): str(lease.get("ip") or "")
        for lease in dhcp.get("leases") or []
        if isinstance(lease, dict) and "." in str(lease.get("ip") or "")
    }
    static_ipv4_by_mac = {
        str(lease.get("mac") or "").lower(): str(lease.get("ip") or "")
        for lease in dhcp.get("static_leases") or []
        if isinstance(lease, dict) and "." in str(lease.get("ip") or "")
    }
    connection = (
        connection_by_mac or _client_connection_details(telemetry_payload)
    ).get(mac_key) or {}
    registry_address = str(item.get("ip_address") or "")
    item["current_ipv4"] = (
        lease_ipv4_by_mac.get(mac_key)
        or static_ipv4_by_mac.get(mac_key)
        or connection.get("ipv4")
        or (registry_address if "." in registry_address else "")
    )
    item["static_ipv4"] = static_ipv4_by_mac.get(mac_key) or ""
    item["ipv6_addresses"] = connection.get("ipv6") or (
        [registry_address] if ":" in registry_address else []
    )
    item["connection_type"] = connection.get("connection_type") or (
        "wired" if connection.get("interface") or item.get("interface") else "unknown"
    )
    item["connection_name"] = connection.get("connection_name") or ""
    item["wifi_ssid"] = connection.get("wifi_ssid") or ""
    item["wifi_band"] = connection.get("wifi_band") or ""
    item["signal_dbm"] = connection.get("signal_dbm")
    item["rx_bitrate"] = connection.get("rx_bitrate")
    item["tx_bitrate"] = connection.get("tx_bitrate")
    return item


@router.get("/{device_id}/clients")
def list_clients(
    device_id: UUID, user: User = Depends(current_user), db: Session = Depends(get_db)
) -> list[dict]:
    get_user_device_or_404(db, user, device_id)
    clients = db.scalars(
        select(NetworkClient)
        .where(NetworkClient.device_id == device_id)
        .order_by(NetworkClient.online.desc(), NetworkClient.last_seen_at.desc())
    ).all()
    response = [client_response(db, client) for client in clients]
    telemetry = latest_device_telemetry(db, device_id)
    telemetry_payload = telemetry.payload if telemetry else {}
    connection_by_mac = _client_connection_details(telemetry_payload)
    for item in response:
        _enrich_client(item, telemetry_payload, connection_by_mac)
    rank = {"online": 0, "recent": 1, "offline": 2}
    response.sort(
        key=lambda item: (
            rank.get(str(item.get("presence_state")), 3),
            str(item.get("display_name") or item.get("hostname") or item.get("mac")),
        )
    )
    return response


@router.get("/{device_id}/clients/{client_id}")
def client_detail(
    device_id: UUID,
    client_id: UUID,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict:
    get_user_device_or_404(db, user, device_id)
    client = get_client(db, device_id, client_id)
    telemetry = latest_device_telemetry(db, device_id)
    return _enrich_client(
        client_response(db, client), telemetry.payload if telemetry else {}
    )


@router.patch("/{device_id}/clients/{client_id}")
@router.put("/{device_id}/clients/{client_id}")
def update_client(
    device_id: UUID,
    client_id: UUID,
    payload: ClientUpdateRequest,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict:
    get_user_device_or_404(db, user, device_id)
    client = get_client(db, device_id, client_id)
    _update_client_record(db, device_id, client, payload)
    audit(
        db,
        user.id,
        "client.update",
        "network_client",
        str(client.id),
        {"mac": client.mac},
    )
    db.commit()
    return client_response(db, client)


@router.post("/{device_id}/clients/{client_id}/configure")
def configure_client(
    device_id: UUID,
    client_id: UUID,
    payload: ClientUpdateRequest,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Persist client settings and queue their router policy atomically."""
    get_user_device_or_404(db, user, device_id)
    client = get_client(db, device_id, client_id)
    _update_client_record(db, device_id, client, payload)
    command = _queue_client_policy(db, device_id, client, user, "api")
    audit(
        db,
        user.id,
        "client.configure",
        "network_client",
        str(client.id),
        {"mac": client.mac, "command_id": str(command.id)},
    )
    db.commit()
    telemetry = latest_device_telemetry(db, device_id)
    return {
        "client": _enrich_client(
            client_response(db, client), telemetry.payload if telemetry else {}
        ),
        "command_id": str(command.id),
        "status": command.status,
    }


@router.get("/{device_id}/clients/{client_id}/activity")
def client_activity(
    device_id: UUID,
    client_id: UUID,
    limit: int = Query(default=50, ge=1, le=200),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> list[dict]:
    get_user_device_or_404(db, user, device_id)
    client = get_client(db, device_id, client_id)
    events = db.scalars(
        select(ClientActivityEvent)
        .where(ClientActivityEvent.client_id == client.id)
        .order_by(ClientActivityEvent.occurred_at.desc())
        .limit(limit)
    ).all()
    return [
        {
            "state": event.state,
            "source": event.source,
            "ip_address": event.ip_address,
            "interface": event.interface,
            "occurred_at": event.occurred_at.isoformat(),
        }
        for event in events
    ]


@router.get("/{device_id}/clients/{client_id}/traffic")
def client_traffic(
    device_id: UUID,
    client_id: UUID,
    limit: int = Query(default=96, ge=1, le=1000),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> list[dict]:
    get_user_device_or_404(db, user, device_id)
    client = get_client(db, device_id, client_id)
    samples = db.scalars(
        select(ClientTrafficSample)
        .where(ClientTrafficSample.client_id == client.id)
        .order_by(ClientTrafficSample.created_at.desc())
        .limit(limit)
    ).all()
    ordered = list(reversed(samples))
    result: list[dict] = []
    previous: ClientTrafficSample | None = None
    for item in ordered:
        result.append(
            {
                "rx_bytes": item.rx_bytes,
                "tx_bytes": item.tx_bytes,
                "rx_delta": max(0, item.rx_bytes - previous.rx_bytes)
                if previous
                else 0,
                "tx_delta": max(0, item.tx_bytes - previous.tx_bytes)
                if previous
                else 0,
                "created_at": item.created_at.isoformat(),
            }
        )
        previous = item
    return result


@router.post("/{device_id}/clients/{client_id}/apply-policy")
def apply_policy(
    device_id: UUID,
    client_id: UUID,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    get_user_device_or_404(db, user, device_id)
    client = get_client(db, device_id, client_id)
    command = _queue_client_policy(db, device_id, client, user, "api")
    audit(
        db,
        user.id,
        "client.policy.apply",
        "network_client",
        str(client.id),
        {"command_id": str(command.id)},
    )
    db.commit()
    return {"command_id": str(command.id), "status": command.status}


@router.delete("/{device_id}/clients/{client_id}")
def delete_client(
    device_id: UUID,
    client_id: UUID,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    """Forget a client and its local history; active clients may be observed again."""
    get_user_device_or_404(db, user, device_id)
    client = get_client(db, device_id, client_id)
    audit(
        db,
        user.id,
        "client.delete",
        "network_client",
        str(client.id),
        {"mac": client.mac},
    )
    db.execute(
        delete(ClientTrafficSample).where(ClientTrafficSample.client_id == client.id)
    )
    db.execute(
        delete(ClientActivityEvent).where(ClientActivityEvent.client_id == client.id)
    )
    db.delete(client)
    db.commit()
    return {"status": "deleted"}


@router.get("/{device_id}/client-profiles")
def list_profiles(
    device_id: UUID, user: User = Depends(current_user), db: Session = Depends(get_db)
) -> list[dict]:
    get_user_device_or_404(db, user, device_id)
    return [
        {"id": str(item.id), "name": item.name, "policy": item.policy}
        for item in db.scalars(
            select(ClientProfile)
            .where(ClientProfile.device_id == device_id)
            .order_by(ClientProfile.name)
        ).all()
    ]


@router.post("/{device_id}/client-profiles")
def create_profile(
    device_id: UUID,
    payload: ClientProfileRequest,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict:
    get_user_device_or_404(db, user, device_id)
    normalized_name = payload.name.strip()
    existing = db.scalars(
        select(ClientProfile).where(
            ClientProfile.device_id == device_id,
            ClientProfile.name == normalized_name,
        )
    ).first()
    if existing:
        raise HTTPException(
            status_code=409, detail="Client profile name already exists"
        )
    profile = ClientProfile(
        id=uuid4(),
        device_id=device_id,
        name=normalized_name,
        policy=validate_client_policy(payload.policy),
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    db.add(profile)
    audit(
        db,
        user.id,
        "client_profile.create",
        "client_profile",
        str(profile.id),
        {"name": profile.name},
    )
    db.commit()
    return {"id": str(profile.id), "name": profile.name, "policy": profile.policy}


def get_profile(db: Session, device_id: UUID, profile_id: UUID) -> ClientProfile:
    profile = db.get(ClientProfile, profile_id)
    if not profile or profile.device_id != device_id:
        raise HTTPException(status_code=404, detail="Client profile not found")
    return profile


@router.put("/{device_id}/client-profiles/{profile_id}")
def update_profile(
    device_id: UUID,
    profile_id: UUID,
    payload: ClientProfileRequest,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict:
    get_user_device_or_404(db, user, device_id)
    profile = get_profile(db, device_id, profile_id)
    normalized_name = payload.name.strip()
    duplicate = db.scalars(
        select(ClientProfile).where(
            ClientProfile.device_id == device_id,
            ClientProfile.name == normalized_name,
            ClientProfile.id != profile.id,
        )
    ).first()
    if duplicate:
        raise HTTPException(
            status_code=409, detail="Client profile name already exists"
        )
    profile.name = normalized_name
    profile.policy = validate_client_policy(payload.policy)
    profile.updated_at = datetime.now(UTC)
    audit(
        db,
        user.id,
        "client_profile.update",
        "client_profile",
        str(profile.id),
        {"name": profile.name},
    )
    db.commit()
    return {"id": str(profile.id), "name": profile.name, "policy": profile.policy}


@router.delete("/{device_id}/client-profiles/{profile_id}")
def delete_profile(
    device_id: UUID,
    profile_id: UUID,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    get_user_device_or_404(db, user, device_id)
    profile = get_profile(db, device_id, profile_id)
    db.delete(profile)
    audit(
        db,
        user.id,
        "client_profile.delete",
        "client_profile",
        str(profile.id),
        {"name": profile.name},
    )
    db.commit()
    return {"status": "deleted"}
