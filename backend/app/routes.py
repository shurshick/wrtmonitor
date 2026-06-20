from datetime import UTC, datetime
import json
import secrets
from typing import Any
from uuid import UUID, uuid4

import jwt
from fastapi import Cookie, Depends, Form, Header, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from .app_factory import app
from .config import APP_NAME, APP_VERSION, Settings, load_settings, validate_server_url
from .db import check_database, get_db
from .models import AppSetting, AuditLog, Device, DeviceCommand, DeviceTelemetry, User
from .security import create_access_token, decode_access_token, hash_password, hash_token, verify_password
from .schemas import AgentRegisterRequest, CommandCreateRequest, CommandResultRequest, DeviceProvisionRequest, LoginRequest, SetupRequest, TelemetryRequest
from .services.commands import create_device_command, expire_old_commands
from .services.devices import get_device_or_404, get_user_device_or_404
from .services.telemetry import build_telemetry_summary
from .web.csrf import generate_csrf_token, verify_csrf_token


ALLOWED_COMMANDS = {
    "router.reboot",
    "wifi.status",
    "wifi.set_enabled",
    "wifi.set_ssid",
    "network.interfaces",
}

TELEMETRY_STALE_SECONDS = 5 * 60


templates = Jinja2Templates(directory="backend/app/templates")


def settings() -> Settings:
    return load_settings()


def now_utc() -> datetime:
    return datetime.now(UTC)


def get_public_server_url(db: Session, config: Settings) -> str | None:
    if config.public_server_url:
        return config.public_server_url
    setting = db.get(AppSetting, "public_server_url")
    return setting.value if setting else None


def has_admin(db: Session) -> bool:
    return db.scalar(select(User.id).limit(1)) is not None


def is_setup_required(db: Session, config: Settings) -> bool:
    return not has_admin(db) or not get_public_server_url(db, config)


def bearer_token(authorization: str | None) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Bearer token required")
    return authorization.removeprefix("Bearer ").strip()


def current_user(
    authorization: str | None = Header(default=None),
    config: Settings = Depends(settings),
    db: Session = Depends(get_db),
) -> User:
    token = bearer_token(authorization)
    try:
        payload = decode_access_token(token, config)
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=401, detail="Invalid access token") from exc
    user = db.get(User, UUID(str(payload.get("sub"))))
    if not user or user.disabled:
        raise HTTPException(status_code=401, detail="Invalid access token")
    return user


def device_from_token(authorization: str | None, db: Session) -> Device:
    token = bearer_token(authorization)
    device = db.scalars(select(Device).where(Device.token_hash == hash_token(token))).first()
    if not device:
        raise HTTPException(status_code=401, detail="Invalid device token")
    return device


def web_user_from_session(session_token: str | None, config: Settings, db: Session) -> User | None:
    if not session_token:
        return None
    try:
        payload = decode_access_token(session_token, config)
    except jwt.PyJWTError:
        return None
    user = db.get(User, UUID(str(payload.get("sub"))))
    if not user or user.disabled:
        return None
    return user


def audit(db: Session, user_id: UUID | None, action: str, object_type: str | None = None, object_id: str | None = None, details: dict[str, Any] | None = None) -> None:
    db.add(AuditLog(id=uuid4(), user_id=user_id, action=action, object_type=object_type, object_id=object_id, details=details, created_at=now_utc()))


def cleanup_device_telemetry(db: Session, device_id: UUID, keep: int) -> None:
    old_ids = [
        row[0]
        for row in db.execute(
            select(DeviceTelemetry.id)
            .where(DeviceTelemetry.device_id == device_id)
            .order_by(DeviceTelemetry.created_at.desc())
            .offset(keep)
        ).all()
    ]
    if old_ids:
        db.execute(delete(DeviceTelemetry).where(DeviceTelemetry.id.in_(old_ids)))


def require_web_csrf(session_token: str | None, csrf_token: str, config: Settings) -> None:
    if not session_token or not verify_csrf_token(session_token, csrf_token, config.jwt_secret):
        raise HTTPException(status_code=403, detail="Invalid CSRF token")


@app.get("/", response_class=HTMLResponse)
def index(request: Request, config: Settings = Depends(settings), db: Session = Depends(get_db), wrtmonitor_session: str | None = Cookie(default=None)):
    if is_setup_required(db, config):
        return RedirectResponse("/setup", status_code=303)
    user = web_user_from_session(wrtmonitor_session, config, db)
    return templates.TemplateResponse(request, "index.html", {"app_name": APP_NAME, "version": APP_VERSION, "authenticated": bool(user), "api_docs_enabled": config.enable_api_docs})


@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request, config: Settings = Depends(settings), db: Session = Depends(get_db)):
    if is_setup_required(db, config):
        return RedirectResponse("/setup", status_code=303)
    return templates.TemplateResponse(request, "login.html", {})


@app.post("/login")
def login_form(request: Request, username: str = Form(...), password: str = Form(...), config: Settings = Depends(settings), db: Session = Depends(get_db)):
    if is_setup_required(db, config):
        return RedirectResponse("/setup", status_code=303)
    user = db.scalars(select(User).where(User.username == username, User.disabled.is_(False))).first()
    if not user or not verify_password(password, user.password_hash):
        return templates.TemplateResponse(request, "message.html", {"title": "Вход не выполнен", "message": "Проверьте логин и пароль.", "link": "/login"}, status_code=401)
    response = RedirectResponse("/devices", status_code=303)
    response.set_cookie(
        "wrtmonitor_session",
        create_access_token(user.id, user.role, config),
        httponly=True,
        samesite="lax",
        max_age=8 * 60 * 60,
    )
    return response


@app.post("/logout")
def logout_form(csrf_token: str = Form(...), config: Settings = Depends(settings), wrtmonitor_session: str | None = Cookie(default=None)) -> RedirectResponse:
    require_web_csrf(wrtmonitor_session, csrf_token, config)
    response = RedirectResponse("/", status_code=303)
    response.delete_cookie("wrtmonitor_session")
    return response


@app.get("/devices", response_class=HTMLResponse)
def devices_page(request: Request, config: Settings = Depends(settings), db: Session = Depends(get_db), wrtmonitor_session: str | None = Cookie(default=None)):
    if is_setup_required(db, config):
        return RedirectResponse("/setup", status_code=303)
    user = web_user_from_session(wrtmonitor_session, config, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    csrf_token = generate_csrf_token(wrtmonitor_session or "", config.jwt_secret)
    devices = db.scalars(select(Device).order_by(Device.created_at.desc())).all()
    return templates.TemplateResponse(request, "devices.html", {"devices": devices, "csrf_token": csrf_token})


@app.get("/devices/{device_id}", response_class=HTMLResponse)
def device_page(request: Request, device_id: UUID, config: Settings = Depends(settings), db: Session = Depends(get_db), wrtmonitor_session: str | None = Cookie(default=None)):
    if is_setup_required(db, config):
        return RedirectResponse("/setup", status_code=303)
    user = web_user_from_session(wrtmonitor_session, config, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    device = get_user_device_or_404(db, user, device_id)
    csrf_token = generate_csrf_token(wrtmonitor_session or "", config.jwt_secret)
    telemetry = db.scalars(
        select(DeviceTelemetry).where(DeviceTelemetry.device_id == device_id).order_by(DeviceTelemetry.created_at.desc()).limit(1)
    ).first()
    payload = telemetry.payload if telemetry else {}
    system = payload.get("system") or {}
    memory = system.get("memory") or {}
    wifi = payload.get("wifi") or {}
    network = payload.get("network") or {}
    radios = wifi.get("radios") or []
    interfaces = network.get("interface") or []
    commands = db.scalars(
        select(DeviceCommand).where(DeviceCommand.device_id == device_id).order_by(DeviceCommand.created_at.desc()).limit(10)
    ).all()
    latest = telemetry.created_at.isoformat() if telemetry else "нет данных"
    age = max(0, int((now_utc() - telemetry.created_at).total_seconds())) if telemetry else None
    return templates.TemplateResponse(request, "device_detail.html", {"device": device, "csrf_token": csrf_token, "latest": latest, "age": age, "system": system, "memory": memory, "radios": radios, "interfaces": interfaces, "commands": commands, "raw_telemetry": json.dumps(payload, ensure_ascii=False, indent=2)})


@app.post("/devices/{device_id}/web-command")
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
    payload: dict[str, Any] = {}
    if command_type == "wifi.set_ssid":
        if not ssid.strip():
            raise HTTPException(status_code=400, detail="SSID is required")
        payload["ssid"] = ssid.strip()
    elif command_type == "wifi.set_enabled":
        payload["enabled"] = enabled.lower() == "true"
    command = create_device_command(db, device_id=device_id, command_type=command_type, payload=payload, created_by=user.id, source="web")
    audit(db, user.id, "command.create", "device_command", str(command.id), {"command_type": command_type, "source": "web"})
    db.commit()
    return RedirectResponse(f"/devices/{device_id}", status_code=303)


@app.post("/devices/{device_id}/delete")
def delete_device_page(device_id: UUID, csrf_token: str = Form(...), config: Settings = Depends(settings), db: Session = Depends(get_db), wrtmonitor_session: str | None = Cookie(default=None)) -> RedirectResponse:
    if is_setup_required(db, config):
        return RedirectResponse("/setup", status_code=303)
    user = web_user_from_session(wrtmonitor_session, config, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    require_web_csrf(wrtmonitor_session, csrf_token, config)
    device = get_user_device_or_404(db, user, device_id)
    if device and device.last_seen_at is None and device.status in {"provisioned", "offline"}:
        db.delete(device)
        db.commit()
    return RedirectResponse("/devices", status_code=303)


@app.get("/setup", response_class=HTMLResponse)
def setup_page(request: Request, config: Settings = Depends(settings), db: Session = Depends(get_db), wrtmonitor_setup_nonce: str | None = Cookie(default=None)) -> HTMLResponse:
    if not is_setup_required(db, config):
        return templates.TemplateResponse(request, "message.html", {"title": "WrtMonitor настроен", "message": "Первичная настройка уже завершена.", "link": "/"})
    nonce = wrtmonitor_setup_nonce or secrets.token_urlsafe(24)
    csrf_token = generate_csrf_token(nonce, config.jwt_secret)
    response = templates.TemplateResponse(request, "setup.html", {"csrf_token": csrf_token})
    response.set_cookie("wrtmonitor_setup_nonce", nonce, httponly=True, samesite="lax", max_age=15 * 60)
    return response


@app.post("/setup")
def setup_form(username: str = Form(...), password: str = Form(...), password_confirm: str = Form(...), server_url: str = Form(...), csrf_token: str = Form(...), config: Settings = Depends(settings), db: Session = Depends(get_db), wrtmonitor_setup_nonce: str | None = Cookie(default=None)):
    if not wrtmonitor_setup_nonce or not verify_csrf_token(wrtmonitor_setup_nonce, csrf_token, config.jwt_secret):
        raise HTTPException(status_code=403, detail="Invalid CSRF token")
    complete_setup(SetupRequest(username=username, password=password, password_confirm=password_confirm, server_url=server_url), config, db)
    response = RedirectResponse("/", status_code=303)
    response.delete_cookie("wrtmonitor_setup_nonce")
    return response


@app.get("/api/v1/setup/status")
def setup_status(config: Settings = Depends(settings), db: Session = Depends(get_db)) -> dict[str, Any]:
    return {
        "setup_required": is_setup_required(db, config),
        "admin_exists": has_admin(db),
        "server_url": get_public_server_url(db, config),
    }


@app.post("/api/v1/setup/complete")
def complete_setup(payload: SetupRequest, config: Settings = Depends(settings), db: Session = Depends(get_db)) -> dict[str, str]:
    if has_admin(db):
        raise HTTPException(status_code=409, detail="Administrator already exists")
    if payload.password != payload.password_confirm:
        raise HTTPException(status_code=400, detail="Passwords do not match")
    server_url = validate_server_url(payload.server_url, config.allow_insecure_local)
    now = now_utc()
    user = User(id=uuid4(), username=payload.username.strip(), password_hash=hash_password(payload.password), role="owner", disabled=False, created_at=now, updated_at=now)
    db.add(user)
    db.flush()
    db.add(AppSetting(key="public_server_url", value=server_url, updated_at=now))
    audit(db, user.id, "setup.complete", "server", None, {"server_url": server_url})
    db.commit()
    return {"server_url": server_url}


@app.post("/api/v1/auth/login")
def login(payload: LoginRequest, config: Settings = Depends(settings), db: Session = Depends(get_db)) -> dict[str, str]:
    if is_setup_required(db, config):
        raise HTTPException(status_code=403, detail="Setup required")
    user = db.scalars(select(User).where(User.username == payload.username, User.disabled.is_(False))).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return {"access_token": create_access_token(user.id, user.role, config), "token_type": "bearer"}


@app.get("/api/v1/devices")
def list_devices(_: User = Depends(current_user), db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    return [
        {
            "id": str(device.id),
            "name": device.name,
            "hostname": device.hostname,
            "model": device.model,
            "firmware": device.firmware,
            "status": device.status,
            "last_seen_at": device.last_seen_at.isoformat() if device.last_seen_at else None,
        }
        for device in db.scalars(select(Device).order_by(Device.created_at.desc())).all()
    ]


@app.get("/api/v1/devices/{device_id}/telemetry/latest")
def latest_device_telemetry(device_id: UUID, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    get_user_device_or_404(db, user, device_id)
    telemetry = db.scalars(
        select(DeviceTelemetry)
        .where(DeviceTelemetry.device_id == device_id)
        .order_by(DeviceTelemetry.created_at.desc())
        .limit(1)
    ).first()
    if not telemetry:
        return {"device_id": str(device_id), "telemetry": None, "created_at": None, "age_seconds": None, "is_stale": False, "source": "agent", "summary": None}
    age_seconds = max(0, int((now_utc() - telemetry.created_at).total_seconds()))
    return {
        "device_id": str(device_id),
        "telemetry": telemetry.payload,
        "created_at": telemetry.created_at.isoformat(),
        "age_seconds": age_seconds,
        "is_stale": age_seconds > TELEMETRY_STALE_SECONDS,
        "source": "agent",
        "summary": build_telemetry_summary(telemetry.payload),
    }


@app.post("/api/v1/devices/provision")
def provision_device(payload: DeviceProvisionRequest, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict[str, str]:
    device_token = secrets.token_urlsafe(32)
    now = now_utc()
    device = db.scalars(
        select(Device)
        .where(Device.hostname == payload.hostname, Device.name == payload.name, Device.model == payload.model)
        .order_by(Device.updated_at.desc())
        .limit(1)
    ).first()
    if device:
        device.firmware = payload.firmware
        device.token_hash = hash_token(device_token)
        device.status = "provisioned"
        device.updated_at = now
    else:
        device = Device(
            id=uuid4(),
            name=payload.name,
            hostname=payload.hostname,
            model=payload.model,
            firmware=payload.firmware,
            token_hash=hash_token(device_token),
            status="provisioned",
            last_seen_at=None,
            created_at=now,
            updated_at=now,
        )
        db.add(device)
    audit(db, user.id, "device.provision", "device", str(device.id), {"hostname": payload.hostname})
    db.commit()
    return {"device_id": str(device.id), "device_token": device_token}


@app.post("/api/v1/agent/register")
def register_agent(payload: AgentRegisterRequest, db: Session = Depends(get_db)) -> dict[str, str]:
    token_digest = hash_token(payload.device_token)
    existing = db.scalars(select(Device).where(Device.token_hash == token_digest)).first()
    if existing:
        return {"device_id": str(existing.id)}
    raise HTTPException(status_code=401, detail="Unknown device token")


@app.post("/api/v1/agent/telemetry")
def agent_telemetry(payload: TelemetryRequest, authorization: str | None = Header(default=None), db: Session = Depends(get_db)) -> dict[str, str]:
    device = device_from_token(authorization, db)
    if device.id != payload.device_id:
        raise HTTPException(status_code=403, detail="Device token mismatch")
    now = now_utc()
    device.status = "online"
    device.last_seen_at = now
    device.updated_at = now
    db.add(DeviceTelemetry(id=uuid4(), device_id=device.id, payload=payload.telemetry, created_at=now))
    db.flush()
    cleanup_device_telemetry(db, device.id, settings().telemetry_retention_per_device)
    db.commit()
    return {"status": "ok"}


@app.post("/api/v1/devices/{device_id}/commands")
def create_command(device_id: UUID, payload: CommandCreateRequest, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict[str, str]:
    if payload.command_type not in ALLOWED_COMMANDS:
        raise HTTPException(status_code=400, detail="Command is not allowed")
    get_user_device_or_404(db, user, device_id)
    command = create_device_command(db, device_id=device_id, command_type=payload.command_type, payload=payload.payload, created_by=user.id, source="api")
    audit(db, user.id, "command.create", "device_command", str(command.id), {"command_type": payload.command_type})
    db.commit()
    return {"command_id": str(command.id), "status": command.status}


@app.get("/api/v1/devices/{device_id}/commands")
def list_device_commands(device_id: UUID, limit: int = 20, status: str | None = None, user: User = Depends(current_user), db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    get_user_device_or_404(db, user, device_id)
    expire_old_commands(db)
    query = select(DeviceCommand).where(DeviceCommand.device_id == device_id)
    if status:
        query = query.where(DeviceCommand.status == status)
    commands = db.scalars(query.order_by(DeviceCommand.created_at.desc()).limit(min(max(limit, 1), 100))).all()
    db.commit()
    def iso(value):
        return value.isoformat() if value else None
    return [{"id": str(command.id), "command_type": command.command_type, "status": command.status,
             "source": command.source, "payload": command.payload, "result": command.result,
             "created_at": iso(command.created_at), "picked_at": iso(command.picked_at),
             "completed_at": iso(command.completed_at), "expires_at": iso(command.expires_at),
             "last_error": command.last_error} for command in commands]


@app.get("/api/v1/agent/commands")
def poll_commands(authorization: str | None = Header(default=None), db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    device = device_from_token(authorization, db)
    expire_old_commands(db)
    commands = db.scalars(select(DeviceCommand).where(DeviceCommand.device_id == device.id, DeviceCommand.status == "queued").order_by(DeviceCommand.created_at.asc()).limit(5)).all()
    for command in commands:
        command.status = "sent"
        command.updated_at = now_utc()
        command.picked_at = now_utc()
        command.retry_count += 1
    db.commit()
    return [{"id": str(command.id), "type": command.command_type, "payload": command.payload} for command in commands]


@app.post("/api/v1/agent/commands/{command_id}/result")
def command_result(command_id: UUID, payload: CommandResultRequest, authorization: str | None = Header(default=None), db: Session = Depends(get_db)) -> dict[str, str]:
    device = device_from_token(authorization, db)
    command = db.get(DeviceCommand, command_id)
    if not command or command.device_id != device.id:
        raise HTTPException(status_code=404, detail="Command not found")
    command.status = "success" if payload.status in {"done", "success"} else "failed"
    command.result = payload.result
    command.updated_at = now_utc()
    command.completed_at = now_utc()
    command.last_error = str(payload.result.get("error")) if isinstance(payload.result, dict) and payload.result.get("error") else None
    audit(db, None, "command.result", "device_command", str(command.id), {"status": command.status})
    db.commit()
    return {"status": "ok"}
