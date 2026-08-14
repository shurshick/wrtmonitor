from fastapi import APIRouter
from .route_shared import (
    APP_VERSION,
    Cookie,
    DEVICE_SECTIONS,
    Depends,
    HTMLResponse,
    HTTPException,
    JSONResponse,
    NETMASK_OPTIONS,
    Query,
    RedirectResponse,
    Request,
    Session,
    Settings,
    TIMEZONE_OPTIONS,
    UUID,
    WIFI_CHANNELS,
    WIFI_COUNTRIES,
    cleanup_device_command_history,
    device_telemetry_history,
    format_timestamp,
    generate_csrf_token,
    get_db,
    get_user_device_or_404,
    is_setup_required,
    json,
    latest_device_telemetry,
    normalize_clients_summary,
    normalize_maintenance_summary,
    normalize_network_summary,
    normalize_services_summary,
    normalize_system_summary,
    normalize_vpn_summary,
    normalize_wifi_summary,
    settings,
    telemetry_alerts,
    templates,
    web_user_from_session,
)
from sqlalchemy import select

from ..models import AuditLog
from ..services.firmware_catalog import firmware_catalog
from ..services.hardware_catalog import hardware_report, hardware_summary
from ..services.health_monitoring import build_health_snapshot
from ..services.policy_catalog import policy_catalog
from .device_overview import daily_overview_context
from .device_context import (
    build_capability_context,
    build_client_context,
    build_command_context,
    build_network_context,
    build_system_view,
)

router = APIRouter()


@router.get("/devices/{device_id}", response_class=HTMLResponse)
def device_page(
    request: Request,
    device_id: UUID,
    section: str = "overview",
    command_page: int = 1,
    config: Settings = Depends(settings),
    db: Session = Depends(get_db),
    wrtmonitor_session: str | None = Cookie(default=None),
):
    if is_setup_required(db, config):
        return RedirectResponse("/setup", status_code=303)
    user = web_user_from_session(wrtmonitor_session, config, db)
    if not user:
        from urllib.parse import quote

        next_url = quote(
            str(request.url.path)
            + ("?" + str(request.url.query) if request.url.query else ""),
            safe="",
        )
        return RedirectResponse(f"/login?next={next_url}", status_code=303)
    device = get_user_device_or_404(db, user, device_id)
    section = section if section in DEVICE_SECTIONS else "overview"
    csrf_token = generate_csrf_token(wrtmonitor_session or "", config.jwt_secret)
    telemetry = latest_device_telemetry(db, device_id)
    payload = telemetry.payload if telemetry else {}
    system = payload.get("system") or {}
    memory = system.get("memory") or {}
    cpu = payload.get("cpu") or {}
    storage = payload.get("storage") or {}
    thermal = payload.get("thermal") or {}
    traffic = payload.get("traffic") or {}
    processes = system.get("processes") or {}
    board = payload.get("board") or {}
    wifi = normalize_wifi_summary(payload)
    agent = dict(payload.get("agent") or {})
    network = normalize_network_summary(payload)
    vpn = normalize_vpn_summary(payload)
    telemetry_clients = normalize_clients_summary(payload)
    maintenance = normalize_maintenance_summary(payload)
    dhcp_config = (
        payload.get("dhcp") or (payload.get("clients") or {}).get("dhcp") or {}
    )
    client_context = build_client_context(db, device_id, dhcp_config, telemetry_clients)
    system_summary = normalize_system_summary(payload)
    services = normalize_services_summary(payload)
    radios = wifi.get("radios") or []
    network_context = build_network_context(payload, network, dhcp_config)
    capability_context = build_capability_context(agent)
    supports = capability_context["supports"]
    command_context = build_command_context(
        db,
        device_id,
        command_page,
        config,
        cleanup=cleanup_device_command_history,
    )
    latest = format_timestamp(telemetry.created_at) if telemetry else "нет данных"
    dashboard_history = device_telemetry_history(db, device_id, 120, range_name="live")
    wan_events = []
    if section == "internet":
        wan_events = [
            {
                "created_at": format_timestamp(item.created_at),
                "details": item.details or {},
            }
            for item in db.scalars(
                select(AuditLog)
                .where(
                    AuditLog.object_type == "device",
                    AuditLog.object_id == str(device_id),
                    AuditLog.action == "wan.failover",
                )
                .order_by(AuditLog.created_at.desc())
                .limit(20)
            ).all()
        ]
    firmware_images = (
        firmware_catalog(payload) if section == "management" else {"images": []}
    )
    hardware_view = hardware_summary(db, device_id, payload)
    overview_context = daily_overview_context(db, device_id, radios)
    db.commit()

    age, system_view = build_system_view(
        telemetry.created_at if telemetry else None,
        system,
        memory,
        cpu,
        storage,
        system_summary,
    )
    return templates.TemplateResponse(
        request,
        "device_detail.html",
        {
            "device": device,
            "server_version": APP_VERSION,
            "section": section,
            "csrf_token": csrf_token,
            "latest": latest,
            "dashboard_history": dashboard_history,
            "health": build_health_snapshot(payload, age, agent=agent),
            "telemetry_alerts": telemetry_alerts(payload, age),
            "age": age,
            "system": system,
            "memory": memory,
            "cpu": cpu,
            "storage": storage,
            "thermal": thermal,
            "hardware_view": hardware_view,
            "traffic": traffic,
            "processes": processes,
            "board": board,
            "agent": agent,
            **capability_context,
            "wifi": wifi,
            "radios": radios,
            **overview_context,
            **network_context,
            "netmask_options": NETMASK_OPTIONS,
            "timezone_options": TIMEZONE_OPTIONS,
            "timezone_names": {item[0] for item in TIMEZONE_OPTIONS},
            "wifi_countries": WIFI_COUNTRIES,
            "wifi_channels": WIFI_CHANNELS,
            "network": network,
            "wan_events": wan_events,
            "policy_catalog": policy_catalog(),
            "firmware_catalog": firmware_images,
            "vpn": vpn,
            **client_context,
            "client_traffic_available": bool(
                supports["client_traffic"]
                and telemetry_clients.get("traffic_available")
            ),
            "client_traffic_status": telemetry_clients.get("traffic_status"),
            "client_traffic_diagnostics": telemetry_clients.get("traffic_diagnostics")
            or {},
            "system_summary": system_summary,
            "system_view": system_view,
            "services": services,
            "maintenance": maintenance,
            "module_labels": {
                "storage": "USB и накопители",
                "smb": "SMB-файлы",
                "nfs": "NFS-файлы",
                "ftp": "FTP-сервер",
                "dlna": "DLNA-медиасервер",
                "printer": "USB-принтер",
                "modem": "LTE/USB-модем",
            },
            **command_context,
            "raw_telemetry": json.dumps(payload, ensure_ascii=False, indent=2),
        },
    )


@router.get("/devices/{device_id}/hardware-report", response_class=JSONResponse)
def download_device_hardware_report(
    device_id: UUID,
    config: Settings = Depends(settings),
    db: Session = Depends(get_db),
    wrtmonitor_session: str | None = Cookie(default=None),
) -> JSONResponse:
    user = web_user_from_session(wrtmonitor_session, config, db)
    if not user:
        raise HTTPException(status_code=401, detail="Требуется авторизация")
    device = get_user_device_or_404(db, user, device_id)
    telemetry = latest_device_telemetry(db, device_id)
    return JSONResponse(
        hardware_report(db, device_id, telemetry.payload if telemetry else {}, device),
        headers={
            "Content-Disposition": f'attachment; filename="wrtmonitor-hardware-{device_id}.json"'
        },
    )


@router.get("/devices/{device_id}/live", response_class=JSONResponse)
def device_live_data(
    device_id: UUID,
    limit: int = 60,
    range_name: str = Query(
        default="live", alias="range", pattern="^(live|24h|7d|30d)$"
    ),
    config: Settings = Depends(settings),
    db: Session = Depends(get_db),
    wrtmonitor_session: str | None = Cookie(default=None),
) -> JSONResponse:
    user = web_user_from_session(wrtmonitor_session, config, db)
    if not user:
        raise HTTPException(status_code=401, detail="Требуется авторизация")
    device = get_user_device_or_404(db, user, device_id)
    return JSONResponse(
        {
            "device_id": str(device.id),
            "status": device.status,
            "last_seen_at": device.last_seen_at.isoformat()
            if device.last_seen_at
            else None,
            "range": range_name,
            "points": device_telemetry_history(
                db, device_id, limit, range_name=range_name
            ),
        }
    )


__all__ = [
    "router",
    "device_page",
    "device_live_data",
    "download_device_hardware_report",
]
