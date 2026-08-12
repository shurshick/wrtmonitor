import asyncio
from io import BytesIO

from fastapi import APIRouter
from .route_shared import (
    ALLOWED_COMMANDS,
    Cookie,
    DEVICE_SECTIONS,
    Depends,
    DeviceCommand,
    File,
    Form,
    HTTPException,
    JSONResponse,
    RedirectResponse,
    Request,
    Response,
    Session,
    Settings,
    UUID,
    UploadFile,
    audit,
    base64,
    binascii,
    build_command_payload_from_web_form,
    build_command_preview,
    create_device_command,
    device_supports,
    ensure_preflight_valid,
    get_db,
    get_user_device_or_404,
    is_setup_required,
    latest_device_telemetry,
    require_web_csrf,
    select,
    settings,
    segno,
    validate_command_request,
    web_user_from_session,
)

router = APIRouter()


@router.post("/devices/{device_id}/wifi-qr.svg")
async def web_wifi_qr(
    device_id: UUID,
    iface: str = Form(...),
    csrf_token: str = Form(...),
    config: Settings = Depends(settings),
    db: Session = Depends(get_db),
    wrtmonitor_session: str | None = Cookie(default=None),
) -> Response:
    user = web_user_from_session(wrtmonitor_session, config, db)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    require_web_csrf(wrtmonitor_session, csrf_token, config)
    get_user_device_or_404(db, user, device_id)
    payload = validate_command_request(
        command_type="wifi.get_qr",
        payload={"iface": iface},
        confirmed=True,
        device_supports=lambda capability: device_supports(db, device_id, capability),
    )
    command = create_device_command(
        db,
        device_id=device_id,
        command_type="wifi.get_qr",
        payload=payload,
        created_by=user.id,
        source="web",
    )
    db.commit()
    from ..services.wifi_qr_broker import consume_wifi_qr_result

    for _ in range(120):
        result = consume_wifi_qr_result(command.id)
        if result is not None:
            wifi_uri = result.get("wifi_uri")
            if not isinstance(wifi_uri, str) or not wifi_uri.startswith("WIFI:"):
                raise HTTPException(
                    status_code=422,
                    detail=str(result.get("error") or "Wi-Fi QR is unavailable"),
                )
            image = BytesIO()
            segno.make(wifi_uri, error="m").save(
                image, kind="svg", scale=7, border=2, xmldecl=False
            )
            return Response(
                content=image.getvalue(),
                media_type="image/svg+xml",
                headers={"Cache-Control": "no-store, private"},
            )
        await asyncio.sleep(0.25)
    raise HTTPException(status_code=504, detail="Router did not return Wi-Fi QR")


@router.get("/devices/{device_id}/commands/{command_id}/download/{kind}")
def download_command_artifact(
    device_id: UUID,
    command_id: UUID,
    kind: str,
    config: Settings = Depends(settings),
    db: Session = Depends(get_db),
    wrtmonitor_session: str | None = Cookie(default=None),
) -> Response:
    user = web_user_from_session(wrtmonitor_session, config, db)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    get_user_device_or_404(db, user, device_id)
    command = db.scalar(
        select(DeviceCommand).where(
            DeviceCommand.id == command_id,
            DeviceCommand.device_id == device_id,
            DeviceCommand.status == "success",
        )
    )
    if command is None or not isinstance(command.result, dict):
        raise HTTPException(status_code=404, detail="Artifact not found")
    field, filename = {
        "backup": ("archive_base64", "wrtmonitor-openwrt-backup.tar.gz"),
        "diagnostics": ("bundle_base64", "wrtmonitor-diagnostics.tar.gz"),
    }.get(kind, ("", ""))
    encoded = command.result.get(field) if field else None
    if not isinstance(encoded, str):
        raise HTTPException(status_code=404, detail="Artifact not found")
    try:
        content = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise HTTPException(status_code=422, detail="Artifact is corrupted") from exc
    return Response(
        content=content,
        media_type="application/gzip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/devices/{device_id}/web-command")
def web_device_command(
    device_id: UUID,
    section: str = "overview",
    command_type: str = Form(...),
    ssid: str = Form(default=""),
    enabled: str = Form(default="true"),
    wifi_password: str = Form(default=""),
    channel: str = Form(default=""),
    country: str = Form(default=""),
    interval_seconds: str = Form(default=""),
    radio: str = Form(default=""),
    iface: str = Form(default=""),
    interface: str = Form(default=""),
    hostname: str = Form(default=""),
    service: str = Form(default=""),
    mac: str = Form(default=""),
    ip: str = Form(default=""),
    protocol: str = Form(default=""),
    ip_address: str = Form(default=""),
    netmask: str = Form(default=""),
    gateway: str = Form(default=""),
    dns: str = Form(default=""),
    username: str = Form(default=""),
    password: str = Form(default=""),
    mtu: str = Form(default=""),
    start: str = Form(default=""),
    limit: str = Form(default=""),
    leasetime: str = Form(default=""),
    servers: str = Form(default=""),
    name: str = Form(default=""),
    external_port: str = Form(default=""),
    internal_ip: str = Form(default=""),
    internal_port: str = Form(default=""),
    blocked: str = Form(default="true"),
    zonename: str = Form(default=""),
    timezone: str = Form(default=""),
    download_kbps: str = Form(default=""),
    upload_kbps: str = Form(default=""),
    htmode: str = Form(default=""),
    txpower: str = Form(default=""),
    network: str = Form(default=""),
    encryption: str = Form(default=""),
    hidden: str = Form(default="false"),
    isolate: str = Form(default="false"),
    ieee80211r: str = Form(default="false"),
    ieee80211k: str = Form(default="false"),
    bss_transition: str = Form(default="false"),
    mobility_domain: str = Form(default=""),
    weekdays: list[str] = Form(default=[]),
    stop: str = Form(default=""),
    mesh_id: str = Form(default=""),
    public_key: str = Form(default=""),
    preshared_key: str = Form(default=""),
    allowed_ips: str = Form(default=""),
    endpoint: str = Form(default=""),
    config_text: str = Form(default=""),
    source: str = Form(default=""),
    destination: str = Form(default=""),
    url: str = Form(default=""),
    sha256: str = Form(default=""),
    archive_base64: str = Form(default=""),
    content: str = Form(default=""),
    pid: str = Form(default=""),
    signal: str = Form(default=""),
    uci_section: str = Form(default=""),
    ports: str = Form(default=""),
    bridge: str = Form(default="false"),
    stp: str = Form(default="false"),
    igmp_snooping: str = Form(default="true"),
    dhcp_enabled: str = Form(default="false"),
    dhcp_start: str = Form(default=""),
    dhcp_limit: str = Form(default=""),
    dhcp_leasetime: str = Form(default=""),
    policy: str = Form(default="guest"),
    vlan_id: str = Form(default=""),
    track_ips: str = Form(default=""),
    check_interval: str = Form(default=""),
    failure_interval: str = Form(default=""),
    recovery_interval: str = Form(default=""),
    confirmed: bool = Form(default=False),
    diagnostics_checks: list[str] = Form(default=[]),
    csrf_token: str = Form(...),
    config: Settings = Depends(settings),
    db: Session = Depends(get_db),
    wrtmonitor_session: str | None = Cookie(default=None),
) -> RedirectResponse:
    if is_setup_required(db, config):
        return RedirectResponse("/setup", status_code=303)
    user = web_user_from_session(wrtmonitor_session, config, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    require_web_csrf(wrtmonitor_session, csrf_token, config)
    get_user_device_or_404(db, user, device_id)
    if command_type not in ALLOWED_COMMANDS:
        raise HTTPException(status_code=400, detail="Unsupported command or device")
    try:
        raw_payload = build_command_payload_from_web_form(
            command_type,
            ssid=ssid,
            enabled=enabled,
            wifi_password=wifi_password,
            channel=channel,
            country=country,
            interval_seconds=interval_seconds,
            radio=radio,
            iface=iface,
            interface=interface,
            hostname=hostname,
            service=service,
            mac=mac,
            ip=ip,
            protocol=protocol,
            ip_address=ip_address,
            netmask=netmask,
            gateway=gateway,
            dns=dns,
            username=username,
            password=password,
            mtu=mtu,
            start=start,
            limit=limit,
            leasetime=leasetime,
            servers=servers,
            name=name,
            external_port=external_port,
            internal_ip=internal_ip,
            internal_port=internal_port,
            blocked=blocked,
            zonename=zonename,
            timezone=timezone,
            download_kbps=download_kbps,
            upload_kbps=upload_kbps,
            htmode=htmode,
            txpower=txpower,
            network=network,
            encryption=encryption,
            hidden=hidden,
            isolate=isolate,
            ieee80211r=ieee80211r,
            ieee80211k=ieee80211k,
            bss_transition=bss_transition,
            mobility_domain=mobility_domain,
            weekdays=weekdays,
            stop=stop,
            mesh_id=mesh_id,
            public_key=public_key,
            preshared_key=preshared_key,
            allowed_ips=allowed_ips,
            endpoint=endpoint,
            config_text=config_text,
            source=source,
            destination=destination,
            url=url,
            sha256=sha256,
            archive_base64=archive_base64,
            content=content,
            pid=pid,
            signal=signal,
            uci_section=uci_section,
            ports=ports,
            bridge=bridge,
            stp=stp,
            igmp_snooping=igmp_snooping,
            dhcp_enabled=dhcp_enabled,
            dhcp_start=dhcp_start,
            dhcp_limit=dhcp_limit,
            dhcp_leasetime=dhcp_leasetime,
            policy=policy,
            vlan_id=vlan_id,
            track_ips=track_ips,
            check_interval=check_interval,
            failure_interval=failure_interval,
            recovery_interval=recovery_interval,
            diagnostics_checks=diagnostics_checks,
        )
        payload = validate_command_request(
            command_type=command_type,
            payload=raw_payload,
            confirmed=confirmed,
            device_supports=lambda capability: device_supports(
                db, device_id, capability
            ),
        )
        telemetry = latest_device_telemetry(db, device_id)
        ensure_preflight_valid(
            command_type,
            payload,
            telemetry.payload if telemetry else {},
        )
    except (ValueError, HTTPException) as exc:
        detail = exc.detail if isinstance(exc, HTTPException) else str(exc)
        raise HTTPException(status_code=400, detail=detail) from exc
    command = create_device_command(
        db,
        device_id=device_id,
        command_type=command_type,
        payload=payload,
        created_by=user.id,
        source="web",
    )
    audit(
        db,
        user.id,
        "command.create",
        "device_command",
        str(command.id),
        {"command_type": command_type, "source": "web", "confirmed": confirmed},
    )
    db.commit()
    section = section if section in DEVICE_SECTIONS else "overview"
    return RedirectResponse(f"/devices/{device_id}?section={section}", status_code=303)


@router.post("/devices/{device_id}/backup/restore")
async def web_restore_router_backup(
    device_id: UUID,
    backup_file: UploadFile = File(...),
    csrf_token: str = Form(...),
    config: Settings = Depends(settings),
    db: Session = Depends(get_db),
    wrtmonitor_session: str | None = Cookie(default=None),
) -> RedirectResponse:
    if is_setup_required(db, config):
        return RedirectResponse("/setup", status_code=303)
    user = web_user_from_session(wrtmonitor_session, config, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    require_web_csrf(wrtmonitor_session, csrf_token, config)
    get_user_device_or_404(db, user, device_id)
    content = await backup_file.read(1_500_001)
    if len(content) > 1_500_000 or not content.startswith(b"\x1f\x8b"):
        raise HTTPException(status_code=400, detail="Invalid backup archive")
    payload = validate_command_request(
        command_type="maintenance.backup.restore",
        payload={"archive_base64": base64.b64encode(content).decode("ascii")},
        confirmed=True,
        device_supports=lambda capability: device_supports(db, device_id, capability),
    )
    command = create_device_command(
        db,
        device_id=device_id,
        command_type="maintenance.backup.restore",
        payload=payload,
        created_by=user.id,
        source="web",
    )
    audit(
        db,
        user.id,
        "command.create",
        "device_command",
        str(command.id),
        {
            "command_type": "maintenance.backup.restore",
            "source": "web",
            "confirmed": True,
        },
    )
    db.commit()
    return RedirectResponse(
        f"/devices/{device_id}?section=maintenance", status_code=303
    )


@router.post("/devices/{device_id}/web-command-preview")
async def web_device_command_preview(
    request: Request,
    device_id: UUID,
    config: Settings = Depends(settings),
    db: Session = Depends(get_db),
    wrtmonitor_session: str | None = Cookie(default=None),
) -> JSONResponse:
    user = web_user_from_session(wrtmonitor_session, config, db)
    if not user:
        return JSONResponse({"detail": "Authentication required"}, status_code=401)
    form = await request.form()
    require_web_csrf(
        wrtmonitor_session,
        str(form.get("csrf_token") or ""),
        config,
    )
    get_user_device_or_404(db, user, device_id)

    def value(name: str, default: str = "") -> str:
        return str(form.get(name) or default)

    command_type = value("command_type")
    try:
        payload = build_command_payload_from_web_form(
            command_type,
            ssid=value("ssid"),
            enabled=value("enabled", "true"),
            wifi_password=value("wifi_password"),
            channel=value("channel"),
            country=value("country"),
            interval_seconds=value("interval_seconds"),
            radio=value("radio"),
            iface=value("iface"),
            interface=value("interface"),
            hostname=value("hostname"),
            service=value("service"),
            mac=value("mac"),
            ip=value("ip"),
            protocol=value("protocol"),
            ip_address=value("ip_address"),
            netmask=value("netmask"),
            gateway=value("gateway"),
            dns=value("dns"),
            username=value("username"),
            password=value("password"),
            mtu=value("mtu"),
            start=value("start"),
            limit=value("limit"),
            leasetime=value("leasetime"),
            servers=value("servers"),
            name=value("name"),
            external_port=value("external_port"),
            internal_ip=value("internal_ip"),
            internal_port=value("internal_port"),
            blocked=value("blocked", "true"),
            zonename=value("zonename"),
            timezone=value("timezone"),
            download_kbps=value("download_kbps"),
            upload_kbps=value("upload_kbps"),
            htmode=value("htmode"),
            txpower=value("txpower"),
            network=value("network"),
            encryption=value("encryption"),
            hidden=value("hidden", "false"),
            isolate=value("isolate", "false"),
            ieee80211r=value("ieee80211r", "false"),
            ieee80211k=value("ieee80211k", "false"),
            bss_transition=value("bss_transition", "false"),
            mobility_domain=value("mobility_domain"),
            weekdays=[str(item) for item in form.getlist("weekdays")],
            stop=value("stop"),
            mesh_id=value("mesh_id"),
            public_key=value("public_key"),
            preshared_key=value("preshared_key"),
            allowed_ips=value("allowed_ips"),
            endpoint=value("endpoint"),
            config_text=value("config_text"),
            source=value("source"),
            destination=value("destination"),
            url=value("url"),
            sha256=value("sha256"),
            archive_base64=value("archive_base64"),
            content=value("content"),
            pid=value("pid"),
            signal=value("signal"),
            uci_section=value("uci_section"),
            diagnostics_checks=[
                str(item) for item in form.getlist("diagnostics_checks")
            ],
        )
        payload = validate_command_request(
            command_type=command_type,
            payload=payload,
            confirmed=True,
            device_supports=lambda capability: device_supports(
                db, device_id, capability
            ),
        )
        telemetry = latest_device_telemetry(db, device_id)
        preview = build_command_preview(
            command_type,
            payload,
            telemetry.payload if telemetry else {},
        )
    except (ValueError, HTTPException) as exc:
        detail = exc.detail if isinstance(exc, HTTPException) else str(exc)
        return JSONResponse({"detail": detail}, status_code=400)
    return JSONResponse(preview)


__all__ = [
    "router",
    "download_command_artifact",
    "web_device_command",
    "web_restore_router_backup",
    "web_device_command_preview",
]
