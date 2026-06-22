from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


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
    confirmed: bool = False


class CommandResultRequest(BaseModel):
    status: str
    result: dict[str, Any] = Field(default_factory=dict)
