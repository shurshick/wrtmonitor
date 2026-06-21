import json
import secrets
from typing import Any
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
    create_device_command,
)
from ..services.devices import get_user_device_or_404
from ..services.audit import audit
from ..services.auth import settings, web_user_from_session
from ..services.setup import complete_setup, is_setup_required
from ..services.telemetry import TELEMETRY_STALE_SECONDS
from .csrf import generate_csrf_token, verify_csrf_token


templates = Jinja2Templates(directory="backend/app/templates")
router = APIRouter()


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
    devices = db.scalars(select(Device).order_by(Device.created_at.desc())).all()
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
    telemetry = db.scalars(
        select(DeviceTelemetry)
        .where(DeviceTelemetry.device_id == device_id)
        .order_by(DeviceTelemetry.created_at.desc())
        .limit(1)
    ).first()
    payload = telemetry.payload if telemetry else {}
    system = payload.get("system") or {}
    memory = system.get("memory") or {}
    cpu = payload.get("cpu") or {}
    storage = payload.get("storage") or {}
    thermal = payload.get("thermal") or {}
    traffic = payload.get("traffic") or {}
    processes = system.get("processes") or {}
    board = payload.get("board") or {}
    wifi = payload.get("wifi") or {}
    network = payload.get("network") or {}
    network_devices = payload.get("network_devices") or {}
    radios = wifi.get("radios") or []
    interfaces = network.get("interface") or []
    commands = db.scalars(
        select(DeviceCommand)
        .where(DeviceCommand.device_id == device_id)
        .order_by(DeviceCommand.created_at.desc())
        .limit(10)
    ).all()
    latest = telemetry.created_at.isoformat() if telemetry else "нет данных"
    from datetime import UTC, datetime

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
            "radios": radios,
            "interfaces": interfaces,
            "network_devices": network_devices,
            "commands": commands,
            "raw_telemetry": json.dumps(payload, ensure_ascii=False, indent=2),
        },
    )


@router.post("/devices/{device_id}/web-command")
def web_device_command(
    device_id: UUID,
    command_type: str = Form(...),
    ssid: str = Form(default=""),
    enabled: str = Form(default="true"),
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
        payload = build_command_payload_from_web_form(command_type, ssid, enabled)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
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
        {"command_type": command_type, "source": "web"},
    )
    db.commit()
    return RedirectResponse(f"/devices/{device_id}", status_code=303)


@router.post("/devices/{device_id}/delete")
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
    if (
        device
        and device.last_seen_at is None
        and device.status in {"provisioned", "offline"}
    ):
        db.delete(device)
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
