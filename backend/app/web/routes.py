from datetime import UTC, datetime
import json
import secrets
from uuid import UUID

from fastapi import APIRouter, Cookie, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import APP_NAME, APP_VERSION, Settings
from ..db import get_db
from ..models import Device, DeviceCommand, DeviceTelemetry, User
from ..security import create_access_token, verify_password
from ..schemas import SetupRequest
from ..services.commands import (
    ALLOWED_COMMANDS,
    build_command_payload_from_web_form,
    command_history_entry,
    create_device_command,
    validate_command_request,
)
from ..services.devices import (
    archive_device_or_409,
    device_supports,
    get_latest_agent_status,
    get_user_device_or_404,
    latest_device_telemetry,
)
from ..security import hash_token
from ..services.audit import audit
from ..services.auth import settings, web_user_from_session
from ..services.setup import complete_setup, is_setup_required
from ..services.telemetry import normalize_network_summary, normalize_wifi_summary
from .csrf import generate_csrf_token, verify_csrf_token


templates = Jinja2Templates(directory="backend/app/templates")
router = APIRouter()


CAPABILITY_GROUPS = {
    "Agent": ("agent.",),
    "Telemetry": ("telemetry.",),
    "Wi-Fi": ("wifi.",),
    "Network": ("network.",),
    "Diagnostics": ("diagnostics.",),
    "System": ("system.",),
}


def format_timestamp(value: datetime | None) -> str:
    if value is None:
        return "нет данных"
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


templates.env.filters["timestamp"] = format_timestamp
templates.env.filters["duration"] = format_duration


def capability_summary(capabilities: dict[str, bool]) -> str:
    if not capabilities:
        return "нет данных"
    enabled = sum(1 for enabled in capabilities.values() if enabled)
    disabled = sum(1 for enabled in capabilities.values() if not enabled)
    return f"{enabled} enabled / {disabled} disabled"


def grouped_capabilities(capabilities: dict[str, bool]) -> list[dict[str, object]]:
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
        disabled_items = [
            name
            for name, enabled in remaining.items()
            if not enabled and name.startswith(prefixes)
        ]
        if enabled_items or disabled_items:
            grouped.append(
                {
                    "title": title,
                    "enabled": enabled_items,
                    "disabled": disabled_items,
                }
            )
            for name in [*enabled_items, *disabled_items]:
                remaining.pop(name, None)
    if remaining:
        grouped.append(
            {
                "title": "Other",
                "enabled": [name for name, enabled in remaining.items() if enabled],
                "disabled": [name for name, enabled in remaining.items() if not enabled],
            }
        )
    return grouped


def capabilities_hint(capabilities: dict[str, bool]) -> str | None:
    if capabilities:
        return None
    return (
        "Агент ещё не передал capabilities. Для управления установите агент rc9 "
        "заново."
    )


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
    agent = get_latest_agent_status(db, device_id)
    network = normalize_network_summary(payload)
    network_devices = payload.get("network_devices") or {}
    radios = wifi.get("radios") or []
    interfaces = network.get("interfaces") or []
    capabilities = agent.get("capabilities") or {}
    capabilities_summary = capability_summary(capabilities)
    capabilities_groups = grouped_capabilities(capabilities)
    capabilities_message = capabilities_hint(capabilities)
    supports = {
        "agent_update": device_supports(db, device_id, "agent.update"),
        "agent_set_interval": device_supports(db, device_id, "agent.set_interval"),
        "agent_rollback": device_supports(db, device_id, "agent.rollback"),
        "diagnostics": device_supports(db, device_id, "diagnostics.check_server"),
        "network_read": device_supports(db, device_id, "network.read"),
        "system_reboot": device_supports(db, device_id, "system.reboot"),
        "wifi_toggle": device_supports(db, device_id, "wifi.enable")
        or device_supports(db, device_id, "wifi.disable"),
        "wifi_ssid": device_supports(db, device_id, "wifi.set_ssid"),
        "wifi_password": device_supports(db, device_id, "wifi.set_password"),
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
    return templates.TemplateResponse(
        request,
        "device_detail.html",
        {
            "device": device,
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
            "commands": command_entries,
            "latest_diagnostics": latest_diagnostics,
            "raw_telemetry": json.dumps(payload, ensure_ascii=False, indent=2),
        },
    )


@router.post("/devices/{device_id}/web-command")
def web_device_command(
    device_id: UUID,
    command_type: str = Form(...),
    ssid: str = Form(default=""),
    enabled: str = Form(default="true"),
    wifi_password: str = Form(default=""),
    interval_seconds: str = Form(default=""),
    radio: str = Form(default=""),
    iface: str = Form(default=""),
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
            interval_seconds=interval_seconds,
            radio=radio,
            iface=iface,
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
    return RedirectResponse(f"/devices/{device_id}", status_code=303)


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


@router.post("/devices/{device_id}/archive")
def archive_device_page(
    request: Request,
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
    try:
        archive_device_or_409(device)
    except HTTPException as exc:
        return templates.TemplateResponse(
            request,
            "message.html",
            {
                "title": "Удаление недоступно",
                "message": exc.detail,
                "link": f"/devices/{device_id}",
            },
            status_code=exc.status_code,
        )
    device.archived_at = datetime.now(UTC)
    device.updated_at = datetime.now(UTC)
    device.token_hash = hash_token(secrets.token_urlsafe(48))
    audit(
        db,
        user.id,
        "device.archive",
        "device",
        str(device.id),
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
