from fastapi import APIRouter
from ..services.client_registry import infer_device_type, validate_device_type
from .route_shared import (
    ClientProfile,
    ClientActivityEvent,
    ClientTrafficSample,
    Cookie,
    Depends,
    Form,
    HTTPException,
    NetworkClient,
    RedirectResponse,
    Session,
    Settings,
    UTC,
    UUID,
    audit,
    create_device_command,
    datetime,
    delete,
    device_supports,
    effective_policy,
    get_db,
    get_user_device_or_404,
    require_web_csrf,
    select,
    settings,
    uuid4,
    validate_client_policy,
    validate_command_request,
    web_user_from_session,
)

router = APIRouter()


@router.post("/devices/{device_id}/clients/{client_id}/policy")
def web_client_policy(
    device_id: UUID,
    client_id: UUID,
    csrf_token: str = Form(...),
    display_name: str = Form(""),
    device_type: str = Form("unknown"),
    profile_id: str = Form(""),
    blocked: bool = Form(False),
    schedule_enabled: bool = Form(False),
    weekdays: str = Form(""),
    start: str = Form(""),
    stop: str = Form(""),
    priority: str = Form("normal"),
    download_kbps: int = Form(0),
    upload_kbps: int = Form(0),
    dns_provider: str = Form("none"),
    config: Settings = Depends(settings),
    db: Session = Depends(get_db),
    wrtmonitor_session: str | None = Cookie(default=None),
) -> RedirectResponse:
    user = web_user_from_session(wrtmonitor_session, config, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    require_web_csrf(wrtmonitor_session, csrf_token, config)
    get_user_device_or_404(db, user, device_id)
    client = db.get(NetworkClient, client_id)
    if not client or client.device_id != device_id:
        raise HTTPException(status_code=404, detail="Client not found")
    policy = validate_client_policy(
        {
            "blocked": blocked,
            "schedule": {
                "enabled": schedule_enabled,
                "weekdays": [
                    item.strip() for item in weekdays.split(",") if item.strip()
                ],
                "start": start,
                "stop": stop,
            },
            "qos": {
                "priority": priority,
                "download_kbps": download_kbps,
                "upload_kbps": upload_kbps,
            },
            "dns": {
                "provider": dns_provider,
                "blocked_domains": [],
            },
        }
    )
    client.display_name = display_name.strip() or None
    selected_type = validate_device_type(device_type)
    if selected_type == "unknown":
        client.device_type = infer_device_type(
            client.display_name, client.hostname, client.vendor
        )
        client.device_type_source = "automatic"
    else:
        client.device_type = selected_type
        client.device_type_source = "user"
    if profile_id:
        try:
            selected_profile_id = UUID(profile_id)
        except ValueError as exc:
            raise HTTPException(
                status_code=422, detail="Invalid client profile"
            ) from exc
        profile = db.get(ClientProfile, selected_profile_id)
        if not profile or profile.device_id != device_id:
            raise HTTPException(status_code=422, detail="Client profile not found")
        client.profile_id = profile.id
        client.policy = {}
    else:
        client.profile_id = None
        client.policy = policy
    client.updated_at = datetime.now(UTC)
    effective = effective_policy(db, client)
    qos = effective.get("qos") or {}
    if (
        int(qos.get("download_kbps") or 0) > 0 or int(qos.get("upload_kbps") or 0) > 0
    ) and not device_supports(db, device_id, "clients.shaping"):
        raise HTTPException(
            status_code=409,
            detail="Для ограничения скорости обновите агент и установите tc-full",
        )
    command_payload = validate_command_request(
        command_type="client.set_policy",
        payload={"mac": client.mac, **effective},
        confirmed=True,
        device_supports=lambda capability: device_supports(db, device_id, capability),
    )
    command = create_device_command(
        db,
        device_id=device_id,
        command_type="client.set_policy",
        payload=command_payload,
        created_by=user.id,
        source="web",
    )
    audit(
        db,
        user.id,
        "client.policy.apply",
        "network_client",
        str(client.id),
        {"command_id": str(command.id)},
    )
    db.commit()
    return RedirectResponse(f"/devices/{device_id}?section=clients", status_code=303)


@router.post("/devices/{device_id}/client-profiles")
def web_create_client_profile(
    device_id: UUID,
    csrf_token: str = Form(...),
    name: str = Form(...),
    blocked: bool = Form(False),
    config: Settings = Depends(settings),
    db: Session = Depends(get_db),
    wrtmonitor_session: str | None = Cookie(default=None),
) -> RedirectResponse:
    user = web_user_from_session(wrtmonitor_session, config, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    require_web_csrf(wrtmonitor_session, csrf_token, config)
    get_user_device_or_404(db, user, device_id)
    normalized_name = name.strip()
    duplicate = db.scalars(
        select(ClientProfile).where(
            ClientProfile.device_id == device_id,
            ClientProfile.name == normalized_name,
        )
    ).first()
    if duplicate:
        raise HTTPException(
            status_code=409, detail="Профиль с таким именем уже существует"
        )
    profile = ClientProfile(
        id=uuid4(),
        device_id=device_id,
        name=normalized_name,
        policy=validate_client_policy({"blocked": blocked}),
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
    return RedirectResponse(f"/devices/{device_id}?section=clients", status_code=303)


@router.post("/devices/{device_id}/client-profiles/{profile_id}/delete")
def web_delete_client_profile(
    device_id: UUID,
    profile_id: UUID,
    csrf_token: str = Form(...),
    config: Settings = Depends(settings),
    db: Session = Depends(get_db),
    wrtmonitor_session: str | None = Cookie(default=None),
) -> RedirectResponse:
    user = web_user_from_session(wrtmonitor_session, config, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    require_web_csrf(wrtmonitor_session, csrf_token, config)
    get_user_device_or_404(db, user, device_id)
    profile = db.get(ClientProfile, profile_id)
    if not profile or profile.device_id != device_id:
        raise HTTPException(status_code=404, detail="Client profile not found")
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
    return RedirectResponse(f"/devices/{device_id}?section=clients", status_code=303)


@router.post("/devices/{device_id}/clients/{client_id}/delete")
def web_delete_client(
    device_id: UUID,
    client_id: UUID,
    csrf_token: str = Form(...),
    config: Settings = Depends(settings),
    db: Session = Depends(get_db),
    wrtmonitor_session: str | None = Cookie(default=None),
) -> RedirectResponse:
    user = web_user_from_session(wrtmonitor_session, config, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    require_web_csrf(wrtmonitor_session, csrf_token, config)
    get_user_device_or_404(db, user, device_id)
    client = db.get(NetworkClient, client_id)
    if not client or client.device_id != device_id:
        raise HTTPException(status_code=404, detail="Client not found")
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
    return RedirectResponse(f"/devices/{device_id}?section=clients", status_code=303)


__all__ = [
    "router",
    "web_client_policy",
    "web_create_client_profile",
    "web_delete_client_profile",
    "web_delete_client",
]
