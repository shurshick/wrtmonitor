from datetime import UTC, datetime
import json
import secrets
from uuid import UUID, uuid4

from fastapi import APIRouter, Cookie, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import APP_NAME, APP_VERSION, Settings
from ..db import get_db
from ..models import ClientProfile, Device, DeviceCommand, NetworkClient, User
from ..security import create_access_token, verify_password
from ..schemas import SetupRequest
from ..services.commands import (
    ALLOWED_COMMANDS,
    build_command_payload_from_web_form,
    command_history_entry,
    create_device_command,
    validate_command_request,
)
from ..services.config_transactions import build_command_preview, ensure_preflight_valid
from ..services.client_registry import (
    client_response,
    effective_policy,
    validate_client_policy,
)
from ..services.devices import (
    delete_device_permanently,
    device_supports,
    get_user_device_or_404,
    latest_device_telemetry,
)
from ..services.audit import audit
from ..services.auth import settings, web_user_from_session
from ..services.setup import complete_setup, is_setup_required
from ..services.telemetry import (
    normalize_clients_summary,
    normalize_network_summary,
    normalize_services_summary,
    normalize_system_summary,
    normalize_wifi_summary,
)
from .csrf import generate_csrf_token, verify_csrf_token


templates = Jinja2Templates(directory="backend/app/templates")
router = APIRouter()

DEVICE_SECTIONS = {"overview", "internet", "clients", "wifi", "system", "management"}


CAPABILITY_GROUPS = {
    "Agent": ("agent.",),
    "Telemetry": ("telemetry.",),
    "Wi-Fi": ("wifi.",),
    "Network": ("network.",),
    "Clients & DHCP": ("clients.", "dhcp."),
    "Diagnostics": ("diagnostics.",),
    "System": ("system.",),
}


def format_timestamp(value: datetime | str | None) -> str:
    if value is None:
        return "нет данных"
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return value
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).strftime("%d.%m.%Y %H:%M:%S UTC")


def format_duration(value: int | None) -> str:
    if value is None:
        return "нет данных"
    days, remainder = divmod(int(value), 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, seconds = divmod(remainder, 60)
    parts: list[str] = []
    if days:
        parts.append(f"{days} д")
    if hours:
        parts.append(f"{hours} ч")
    if minutes:
        parts.append(f"{minutes} мин")
    if seconds or not parts:
        parts.append(f"{seconds} сек")
    return " ".join(parts)


def format_size_kb(value: int | float | None) -> str:
    if value is None:
        return "нет данных"
    size = float(value)
    if size >= 1024 * 1024:
        return f"{size / 1024 / 1024:.1f} ГБ"
    if size >= 1024:
        return f"{size / 1024:.0f} МБ"
    return f"{size:.0f} КБ"


def format_bytes(value: int | float | None) -> str:
    if value is None:
        return "нет данных"
    size = float(value)
    units = ("Б", "КБ", "МБ", "ГБ", "ТБ")
    unit = units[0]
    for unit in units:
        if abs(size) < 1024 or unit == units[-1]:
            break
        size /= 1024
    return f"{size:.1f} {unit}" if unit != "Б" else f"{size:.0f} {unit}"


def percent(used: int | float | None, total: int | float | None) -> int:
    if not total:
        return 0
    return max(0, min(100, round(float(used or 0) / float(total) * 100)))


def format_device_status(value: str | None) -> str:
    return {
        "online": "В сети",
        "offline": "Нет связи",
        "provisioned": "Ожидает подключения",
        "disconnecting": "Отключается",
        "disabled": "Отключён",
    }.get(str(value or "").lower(), value or "Неизвестно")


templates.env.filters["timestamp"] = format_timestamp
templates.env.filters["duration"] = format_duration
templates.env.filters["size_kb"] = format_size_kb
templates.env.filters["bytes"] = format_bytes
templates.env.filters["status_label"] = format_device_status


def capability_summary(capabilities: dict[str, bool]) -> str:
    if not capabilities:
        return "нет данных"
    enabled = sum(1 for enabled in capabilities.values() if enabled)
    disabled = sum(1 for enabled in capabilities.values() if not enabled)
    return f"{enabled} enabled / {disabled} disabled"


def grouped_capabilities(
    capabilities: dict[str, bool], details: dict[str, dict[str, object]] | None = None
) -> list[dict[str, object]]:
    grouped: list[dict[str, object]] = []
    if not capabilities:
        return grouped
    remaining = dict(sorted(capabilities.items()))
    for title, prefixes in CAPABILITY_GROUPS.items():
        enabled_items = [
            name
            for name, enabled in remaining.items()
            if enabled and name.startswith(prefixes)
        ]
        disabled_names = [
            name
            for name, enabled in remaining.items()
            if not enabled and name.startswith(prefixes)
        ]
        disabled_items = [
            {
                "name": name,
                "reason": str(
                    (details or {}).get(name, {}).get("reason") or "недоступно"
                ),
            }
            for name in disabled_names
        ]
        if enabled_items or disabled_names:
            grouped.append(
                {
                    "title": title,
                    "enabled": enabled_items,
                    "disabled": disabled_items,
                }
            )
            for name in [*enabled_items, *disabled_names]:
                remaining.pop(name, None)
    if remaining:
        grouped.append(
            {
                "title": "Other",
                "enabled": [name for name, enabled in remaining.items() if enabled],
                "disabled": [
                    {
                        "name": name,
                        "reason": str(
                            (details or {}).get(name, {}).get("reason") or "недоступно"
                        ),
                    }
                    for name, enabled in remaining.items()
                    if not enabled
                ],
            }
        )
    return grouped


def capabilities_hint(capabilities: dict[str, bool]) -> str | None:
    if capabilities:
        return None
    return "Агент ещё не передал capabilities. Обновите или переустановите агент."


def require_web_csrf(
    session_token: str | None, csrf_token: str, config: Settings
) -> None:
    if not session_token or not verify_csrf_token(
        session_token, csrf_token, config.jwt_secret
    ):
        raise HTTPException(status_code=403, detail="Invalid CSRF token")


@router.get("/", response_class=HTMLResponse)
def index(
    request: Request,
    config: Settings = Depends(settings),
    db: Session = Depends(get_db),
    wrtmonitor_session: str | None = Cookie(default=None),
):
    if is_setup_required(db, config):
        return RedirectResponse("/setup", status_code=303)
    user = web_user_from_session(wrtmonitor_session, config, db)
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "app_name": APP_NAME,
            "version": APP_VERSION,
            "authenticated": bool(user),
            "api_docs_enabled": config.enable_api_docs,
        },
    )


@router.get("/login", response_class=HTMLResponse)
def login_page(
    request: Request,
    config: Settings = Depends(settings),
    db: Session = Depends(get_db),
):
    if is_setup_required(db, config):
        return RedirectResponse("/setup", status_code=303)
    return templates.TemplateResponse(request, "login.html", {})


@router.post("/login")
def login_form(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    config: Settings = Depends(settings),
    db: Session = Depends(get_db),
):
    if is_setup_required(db, config):
        return RedirectResponse("/setup", status_code=303)
    user = db.scalars(
        select(User).where(User.username == username, User.disabled.is_(False))
    ).first()
    if not user or not verify_password(password, user.password_hash):
        return templates.TemplateResponse(
            request,
            "message.html",
            {
                "title": "Вход не выполнен",
                "message": "Проверьте логин и пароль.",
                "link": "/login",
            },
            status_code=401,
        )
    response = RedirectResponse("/devices", status_code=303)
    response.set_cookie(
        "wrtmonitor_session",
        create_access_token(user.id, user.role, config),
        httponly=True,
        samesite="lax",
        max_age=8 * 60 * 60,
    )
    return response


@router.post("/logout")
def logout_form(
    csrf_token: str = Form(...),
    config: Settings = Depends(settings),
    wrtmonitor_session: str | None = Cookie(default=None),
) -> RedirectResponse:
    require_web_csrf(wrtmonitor_session, csrf_token, config)
    response = RedirectResponse("/", status_code=303)
    response.delete_cookie("wrtmonitor_session")
    return response


@router.get("/devices", response_class=HTMLResponse)
def devices_page(
    request: Request,
    config: Settings = Depends(settings),
    db: Session = Depends(get_db),
    wrtmonitor_session: str | None = Cookie(default=None),
):
    if is_setup_required(db, config):
        return RedirectResponse("/setup", status_code=303)
    user = web_user_from_session(wrtmonitor_session, config, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    csrf_token = generate_csrf_token(wrtmonitor_session or "", config.jwt_secret)
    devices = db.scalars(
        select(Device)
        .where(Device.archived_at.is_(None))
        .order_by(Device.created_at.desc())
    ).all()
    return templates.TemplateResponse(
        request, "devices.html", {"devices": devices, "csrf_token": csrf_token}
    )


@router.get("/devices/{device_id}", response_class=HTMLResponse)
def device_page(
    request: Request,
    device_id: UUID,
    section: str = "overview",
    config: Settings = Depends(settings),
    db: Session = Depends(get_db),
    wrtmonitor_session: str | None = Cookie(default=None),
):
    if is_setup_required(db, config):
        return RedirectResponse("/setup", status_code=303)
    user = web_user_from_session(wrtmonitor_session, config, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
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
    telemetry_clients = normalize_clients_summary(payload)
    registry_clients = db.scalars(
        select(NetworkClient)
        .where(NetworkClient.device_id == device_id)
        .order_by(NetworkClient.online.desc(), NetworkClient.last_seen_at.desc())
    ).all()
    clients = [client_response(db, item) for item in registry_clients]
    client_profiles = db.scalars(
        select(ClientProfile)
        .where(ClientProfile.device_id == device_id)
        .order_by(ClientProfile.name)
    ).all()
    system_summary = normalize_system_summary(payload)
    services = normalize_services_summary(payload)
    network_devices = payload.get("network_devices") or {}
    radios = wifi.get("radios") or []
    interfaces = network.get("interfaces") or []
    capabilities = agent.get("capabilities") or {}
    capability_details = agent.get("capability_details") or {}
    capabilities_summary = capability_summary(capabilities)
    capabilities_groups = grouped_capabilities(capabilities, capability_details)
    capabilities_message = capabilities_hint(capabilities)

    def has(name: str) -> bool:
        return bool(capabilities.get(name, False))

    supports = {
        "agent_update": has("agent.update"),
        "agent_set_interval": has("agent.set_interval"),
        "agent_rollback": has("agent.rollback"),
        "diagnostics": has("diagnostics.check_server"),
        "network_read": has("network.read"),
        "network_interface_restart": has("network.interface_restart"),
        "network_restart": has("network.restart"),
        "network_wan_configure": has("network.wan.configure"),
        "network_lan_configure": has("network.lan.configure"),
        "clients_read": has("clients.read"),
        "clients_block": has("clients.block"),
        "clients_policy": has("clients.policy"),
        "qos_sqm": has("qos.sqm"),
        "dhcp_set_lease": has("dhcp.set_lease"),
        "dhcp_delete_lease": has("dhcp.delete_lease"),
        "dhcp_configure": has("dhcp.configure"),
        "dns_configure": has("dns.configure"),
        "firewall_port_forward": has("firewall.port_forward"),
        "system_reboot": has("system.reboot"),
        "system_set_hostname": has("system.set_hostname"),
        "system_restart_service": has("system.restart_service"),
        "wifi_toggle": has("wifi.enable") or has("wifi.disable"),
        "wifi_ssid": has("wifi.set_ssid"),
        "wifi_password": has("wifi.set_password"),
        "wifi_channel": has("wifi.set_channel"),
        "wifi_country": has("wifi.set_country"),
        "wifi_guest": has("wifi.guest"),
        "wifi_radio_configure": has("wifi.radio.configure"),
        "wifi_manage_ssid": has("wifi.manage_ssid"),
        "wifi_schedule": has("wifi.schedule"),
        "wifi_roaming": has("wifi.roaming"),
        "wifi_mesh": has("wifi.mesh"),
        "wifi_stations": has("telemetry.wifi.stations"),
        "system_timezone": has("system.set_timezone"),
        "system_ntp": has("system.set_ntp"),
    }
    commands = db.scalars(
        select(DeviceCommand)
        .where(DeviceCommand.device_id == device_id)
        .order_by(DeviceCommand.created_at.desc())
        .limit(10)
    ).all()
    command_entries = [command_history_entry(command) for command in commands]
    latest_diagnostics = next(
        (
            command
            for command in command_entries
            if command["command_type"] == "diagnostics.run"
        ),
        None,
    )
    latest = format_timestamp(telemetry.created_at) if telemetry else "нет данных"

    age = (
        max(0, int((datetime.now(UTC) - telemetry.created_at).total_seconds()))
        if telemetry
        else None
    )
    memory_total = int(memory.get("total_kb", 0) or 0)
    memory_available = int(memory.get("available_kb", memory.get("free_kb", 0)) or 0)
    memory_used = max(0, memory_total - memory_available)
    storage_total = int(storage.get("total_kb", 0) or 0)
    storage_used = int(storage.get("used_kb", 0) or 0)
    conntrack_count = int(system_summary.get("conntrack_count", 0) or 0)
    conntrack_max = int(system_summary.get("conntrack_max", 0) or 0)
    system_view = {
        "memory_total": memory_total,
        "memory_available": memory_available,
        "memory_used": memory_used,
        "memory_percent": percent(memory_used, memory_total),
        "storage_total": storage_total,
        "storage_used": storage_used,
        "storage_percent": percent(storage_used, storage_total),
        "conntrack_percent": percent(conntrack_count, conntrack_max),
        "telemetry_state": "Актуальные данные"
        if age is not None and age <= 120
        else "Данные устарели",
    }
    return templates.TemplateResponse(
        request,
        "device_detail.html",
        {
            "device": device,
            "server_version": APP_VERSION,
            "section": section,
            "csrf_token": csrf_token,
            "latest": latest,
            "age": age,
            "system": system,
            "memory": memory,
            "cpu": cpu,
            "storage": storage,
            "thermal": thermal,
            "traffic": traffic,
            "processes": processes,
            "board": board,
            "agent": agent,
            "capabilities": capabilities,
            "capabilities_summary": capabilities_summary,
            "capabilities_groups": capabilities_groups,
            "capabilities_message": capabilities_message,
            "supports": supports,
            "radios": radios,
            "interfaces": interfaces,
            "network_devices": network_devices,
            "clients": clients,
            "client_profiles": client_profiles,
            "client_count": len(clients)
            if clients
            else telemetry_clients.get("count", 0),
            "system_summary": system_summary,
            "system_view": system_view,
            "services": services,
            "commands": command_entries,
            "latest_diagnostics": latest_diagnostics,
            "raw_telemetry": json.dumps(payload, ensure_ascii=False, indent=2),
        },
    )


@router.post("/devices/{device_id}/clients/{client_id}/policy")
def web_client_policy(
    device_id: UUID,
    client_id: UUID,
    csrf_token: str = Form(...),
    display_name: str = Form(""),
    profile_id: str = Form(""),
    blocked: bool = Form(False),
    schedule_enabled: bool = Form(False),
    weekdays: str = Form(""),
    start: str = Form(""),
    stop: str = Form(""),
    priority: str = Form("normal"),
    download_kbps: int = Form(0),
    upload_kbps: int = Form(0),
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
        }
    )
    client.display_name = display_name.strip() or None
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
    command_payload = validate_command_request(
        command_type="client.set_policy",
        payload={"mac": client.mac, **effective_policy(db, client)},
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


@router.post("/devices/{device_id}/disconnect")
def disconnect_device_page(
    device_id: UUID,
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
    device = get_user_device_or_404(db, user, device_id)
    if device.status not in {"disabled", "disconnecting"}:
        command = create_device_command(
            db,
            device_id=device.id,
            command_type="agent.disconnect",
            payload={},
            created_by=user.id,
            source="web",
        )
        device.status = "disconnecting"
        audit(
            db,
            user.id,
            "device.disconnect",
            "device",
            str(device.id),
            {"command_id": str(command.id), "source": "web"},
        )
        db.commit()
    return RedirectResponse(f"/devices/{device_id}", status_code=303)


@router.post("/devices/{device_id}/delete")
@router.post("/devices/{device_id}/archive", deprecated=True)
def delete_device_page(
    device_id: UUID,
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
    device = get_user_device_or_404(db, user, device_id)
    delete_device_permanently(db, device)
    audit(
        db,
        user.id,
        "device.delete",
        None,
        None,
        {"source": "web"},
    )
    db.commit()
    return RedirectResponse("/devices", status_code=303)


@router.get("/setup", response_class=HTMLResponse)
def setup_page(
    request: Request,
    config: Settings = Depends(settings),
    db: Session = Depends(get_db),
    wrtmonitor_setup_nonce: str | None = Cookie(default=None),
) -> HTMLResponse:
    if not is_setup_required(db, config):
        return templates.TemplateResponse(
            request,
            "message.html",
            {
                "title": "WrtMonitor настроен",
                "message": "Первичная настройка уже завершена.",
                "link": "/",
            },
        )
    nonce = wrtmonitor_setup_nonce or secrets.token_urlsafe(24)
    csrf_token = generate_csrf_token(nonce, config.jwt_secret)
    response = templates.TemplateResponse(
        request, "setup.html", {"csrf_token": csrf_token}
    )
    response.set_cookie(
        "wrtmonitor_setup_nonce", nonce, httponly=True, samesite="lax", max_age=15 * 60
    )
    return response


@router.post("/setup")
def setup_form(
    username: str = Form(...),
    password: str = Form(...),
    password_confirm: str = Form(...),
    server_url: str = Form(...),
    csrf_token: str = Form(...),
    config: Settings = Depends(settings),
    db: Session = Depends(get_db),
    wrtmonitor_setup_nonce: str | None = Cookie(default=None),
):
    if not wrtmonitor_setup_nonce or not verify_csrf_token(
        wrtmonitor_setup_nonce, csrf_token, config.jwt_secret
    ):
        raise HTTPException(status_code=403, detail="Invalid CSRF token")
    complete_setup(
        SetupRequest(
            username=username,
            password=password,
            password_confirm=password_confirm,
            server_url=server_url,
        ),
        config,
        db,
    )
    response = RedirectResponse("/", status_code=303)
    response.delete_cookie("wrtmonitor_setup_nonce")
    return response
