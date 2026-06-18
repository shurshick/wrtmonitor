from datetime import UTC, datetime
import secrets
from typing import Any
from uuid import UUID, uuid4

import jwt
import uvicorn
from fastapi import Depends, FastAPI, Form, Header, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import APP_NAME, APP_VERSION, Settings, load_settings, validate_server_url
from .db import check_database, get_db, init_db
from .models import AppSetting, AuditLog, Device, DeviceCommand, DeviceTelemetry, User
from .security import create_access_token, decode_access_token, hash_password, hash_token, verify_password


ALLOWED_COMMANDS = {
    "router.reboot",
    "wifi.status",
    "wifi.set_enabled",
    "wifi.set_ssid",
    "network.interfaces",
}


app = FastAPI(title=APP_NAME, version=APP_VERSION)


class LoginRequest(BaseModel):
    username: str
    password: str


class SetupRequest(BaseModel):
    username: str = Field(min_length=3, max_length=120)
    password: str = Field(min_length=8, max_length=256)
    password_confirm: str = Field(min_length=8, max_length=256)
    server_url: str


class AgentRegisterRequest(BaseModel):
    device_token: str = Field(min_length=12)
    name: str | None = None
    hostname: str
    model: str | None = None
    firmware: str | None = None


class DeviceProvisionRequest(BaseModel):
    name: str | None = None
    hostname: str
    model: str | None = None
    firmware: str | None = None


class TelemetryRequest(BaseModel):
    device_id: UUID
    telemetry: dict[str, Any]


class CommandCreateRequest(BaseModel):
    command_type: str
    payload: dict[str, Any] = Field(default_factory=dict)


class CommandResultRequest(BaseModel):
    status: str
    result: dict[str, Any] = Field(default_factory=dict)


def settings() -> Settings:
    return load_settings()


@app.on_event("startup")
def startup() -> None:
    init_db()
    check_database()


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


def audit(db: Session, user_id: UUID | None, action: str, object_type: str | None = None, object_id: str | None = None, details: dict[str, Any] | None = None) -> None:
    db.add(AuditLog(id=uuid4(), user_id=user_id, action=action, object_type=object_type, object_id=object_id, details=details, created_at=now_utc()))


@app.get("/health")
def health() -> dict[str, str]:
    check_database()
    return {"status": "ok", "database": "postgresql"}


@app.get("/", response_class=HTMLResponse)
def index(config: Settings = Depends(settings), db: Session = Depends(get_db)):
    if is_setup_required(db, config):
        return RedirectResponse("/setup", status_code=303)
    return HTMLResponse(
        f"""
        <html lang="ru"><body>
          <h1>{APP_NAME}</h1>
          <p>Сервер работает. Версия: {APP_VERSION}</p>
          <p><a href="/docs">API</a></p>
        </body></html>
        """
    )


@app.get("/setup", response_class=HTMLResponse)
def setup_page(config: Settings = Depends(settings), db: Session = Depends(get_db)) -> HTMLResponse:
    if not is_setup_required(db, config):
        return HTMLResponse("<html><body><h1>wrtmonitor настроен</h1></body></html>")
    return HTMLResponse(
        """
        <html lang="ru"><body>
          <h1>Первая настройка wrtmonitor</h1>
          <form method="post" action="/setup">
            <p><input name="username" placeholder="Администратор" required minlength="3"></p>
            <p><input name="password" type="password" placeholder="Пароль" required minlength="8"></p>
            <p><input name="password_confirm" type="password" placeholder="Повторите пароль" required minlength="8"></p>
            <p><input name="server_url" placeholder="https://monitor.example.ru" required></p>
            <p><button type="submit">Создать</button></p>
          </form>
        </body></html>
        """
    )


@app.post("/setup")
def setup_form(username: str = Form(...), password: str = Form(...), password_confirm: str = Form(...), server_url: str = Form(...), config: Settings = Depends(settings), db: Session = Depends(get_db)):
    complete_setup(SetupRequest(username=username, password=password, password_confirm=password_confirm, server_url=server_url), config, db)
    return RedirectResponse("/", status_code=303)


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


@app.post("/api/v1/devices/provision")
def provision_device(payload: DeviceProvisionRequest, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict[str, str]:
    device_token = secrets.token_urlsafe(32)
    now = now_utc()
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
    db.commit()
    return {"status": "ok"}


@app.post("/api/v1/devices/{device_id}/commands")
def create_command(device_id: UUID, payload: CommandCreateRequest, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict[str, str]:
    if payload.command_type not in ALLOWED_COMMANDS:
        raise HTTPException(status_code=400, detail="Command is not allowed")
    if not db.get(Device, device_id):
        raise HTTPException(status_code=404, detail="Device not found")
    now = now_utc()
    command = DeviceCommand(id=uuid4(), device_id=device_id, command_type=payload.command_type, payload=payload.payload, status="queued", result=None, created_by=user.id, created_at=now, updated_at=now)
    db.add(command)
    audit(db, user.id, "command.create", "device_command", str(command.id), {"command_type": payload.command_type})
    db.commit()
    return {"command_id": str(command.id), "status": command.status}


@app.get("/api/v1/agent/commands")
def poll_commands(authorization: str | None = Header(default=None), db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    device = device_from_token(authorization, db)
    commands = db.scalars(select(DeviceCommand).where(DeviceCommand.device_id == device.id, DeviceCommand.status == "queued").order_by(DeviceCommand.created_at.asc()).limit(5)).all()
    for command in commands:
        command.status = "sent"
        command.updated_at = now_utc()
    db.commit()
    return [{"id": str(command.id), "type": command.command_type, "payload": command.payload} for command in commands]


@app.post("/api/v1/agent/commands/{command_id}/result")
def command_result(command_id: UUID, payload: CommandResultRequest, authorization: str | None = Header(default=None), db: Session = Depends(get_db)) -> dict[str, str]:
    device = device_from_token(authorization, db)
    command = db.get(DeviceCommand, command_id)
    if not command or command.device_id != device.id:
        raise HTTPException(status_code=404, detail="Command not found")
    command.status = payload.status
    command.result = payload.result
    command.updated_at = now_utc()
    audit(db, None, "command.result", "device_command", str(command.id), {"status": payload.status})
    db.commit()
    return {"status": "ok"}


if __name__ == "__main__":
    config = load_settings()
    uvicorn.run("backend.app.main:app", host=config.bind_host, port=config.bind_port)
