from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str
    password: str


class RefreshTokenRequest(BaseModel):
    refresh_token: str = Field(min_length=20)


class MobilePairingExchangeRequest(BaseModel):
    pairing_token: str = Field(min_length=32, max_length=256)
    client_name: str = Field(default="WrtMonitor Android", min_length=1, max_length=160)


class PasswordChangeRequest(BaseModel):
    current_password: str = Field(min_length=8, max_length=256)
    new_password: str = Field(min_length=12, max_length=256)
    new_password_confirm: str = Field(min_length=12, max_length=256)


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
    confirmed: bool = False


class CommandResultRequest(BaseModel):
    status: str
    result: dict[str, Any] = Field(default_factory=dict)


class ClientUpdateRequest(BaseModel):
    display_name: str | None = Field(default=None, max_length=120)
    profile_id: UUID | None = None
    policy: dict[str, Any] | None = None


class ClientProfileRequest(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    policy: dict[str, Any] = Field(default_factory=dict)
