from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    username: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[str] = mapped_column(String(40), nullable=False, default="owner")
    disabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


class AppSetting(Base):
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(120), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


class UserSession(Base):
    __tablename__ = "user_sessions"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    refresh_token_hash: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    client_type: Mapped[str] = mapped_column(
        String(40), nullable=False, default="password"
    )
    client_name: Mapped[str | None] = mapped_column(String(160))
    ip_address: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    last_used_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class MobilePairingToken(Base):
    __tablename__ = "mobile_pairing_tokens"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    token_hash: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    server_url: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    used_session_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("user_sessions.id", ondelete="SET NULL"),
    )


class MobilePairingAttempt(Base):
    __tablename__ = "mobile_pairing_attempts"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    identity_hash: Mapped[str] = mapped_column(Text, nullable=False)
    token_hash: Mapped[str] = mapped_column(Text, nullable=False)
    accepted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


class AuthAttempt(Base):
    __tablename__ = "auth_attempts"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    identity_hash: Mapped[str] = mapped_column(Text, nullable=False)
    ip_hash: Mapped[str] = mapped_column(Text, nullable=False)
    accepted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


class DeviceGroup(Base):
    __tablename__ = "device_groups"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


class Device(Base):
    __tablename__ = "devices"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    group_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("device_groups.id", ondelete="SET NULL"),
    )
    name: Mapped[str | None] = mapped_column(String(120))
    hostname: Mapped[str | None] = mapped_column(String(120))
    model: Mapped[str | None] = mapped_column(String(160))
    firmware: Mapped[str | None] = mapped_column(String(160))
    token_hash: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    previous_token_hash: Mapped[str | None] = mapped_column(Text)
    previous_token_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    token_rollback_hash: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="offline")
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class DeviceTelemetry(Base):
    __tablename__ = "device_telemetry"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    device_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("devices.id", ondelete="CASCADE"),
        nullable=False,
    )
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


class DeviceTelemetryMetric(Base):
    __tablename__ = "device_telemetry_metrics"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    device_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("devices.id", ondelete="CASCADE"),
        nullable=False,
    )
    rx_bps: Mapped[int | None] = mapped_column(BigInteger)
    tx_bps: Mapped[int | None] = mapped_column(BigInteger)
    rx_bytes: Mapped[int | None] = mapped_column(BigInteger)
    tx_bytes: Mapped[int | None] = mapped_column(BigInteger)
    load_1m: Mapped[float | None] = mapped_column(Float)
    memory_percent: Mapped[float | None] = mapped_column(Float)
    client_count: Mapped[int | None] = mapped_column(Integer)
    interfaces: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    wifi: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


class HardwareProfile(Base):
    __tablename__ = "hardware_profiles"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    profile_key: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    vendor: Mapped[str] = mapped_column(String(120), nullable=False)
    model: Mapped[str] = mapped_column(String(160), nullable=False)
    board_names: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    compatibles: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    target: Mapped[str | None] = mapped_column(String(120))
    soc_vendor: Mapped[str | None] = mapped_column(String(120))
    soc_model: Mapped[str | None] = mapped_column(String(120))
    cpu_vendor: Mapped[str | None] = mapped_column(String(120))
    cpu_model: Mapped[str | None] = mapped_column(String(160))
    cpu_architecture: Mapped[str | None] = mapped_column(String(80))
    cpu_cores: Mapped[int | None] = mapped_column(Integer)
    cpu_max_mhz: Mapped[int | None] = mapped_column(Integer)
    sensor_roles: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    source_url: Mapped[str | None] = mapped_column(Text)
    origin: Mapped[str] = mapped_column(String(40), nullable=False, default="builtin")
    verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    observation_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    first_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    catalog_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


class DeviceHardwareIdentity(Base):
    __tablename__ = "device_hardware_identities"

    device_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("devices.id", ondelete="CASCADE"),
        primary_key=True,
    )
    profile_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("hardware_profiles.id", ondelete="SET NULL")
    )
    observed: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    resolved: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    match_method: Mapped[str | None] = mapped_column(String(80))
    match_confidence: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


class HardwareSensorSample(Base):
    __tablename__ = "hardware_sensor_samples"
    __table_args__ = (
        Index("ix_hardware_sensor_device_time", "device_id", "observed_at"),
        Index("ix_hardware_sensor_device_key", "device_id", "sensor_key"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    device_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("devices.id", ondelete="CASCADE"),
        nullable=False,
    )
    sensor_key: Mapped[str] = mapped_column(String(160), nullable=False)
    role: Mapped[str | None] = mapped_column(String(80))
    label: Mapped[str] = mapped_column(String(160), nullable=False)
    subsystem: Mapped[str] = mapped_column(String(40), nullable=False)
    milli_celsius: Mapped[int] = mapped_column(Integer, nullable=False)
    warning_milli_celsius: Mapped[int | None] = mapped_column(Integer)
    critical_milli_celsius: Mapped[int | None] = mapped_column(Integer)
    observed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


class DeviceCommand(Base):
    __tablename__ = "device_commands"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    device_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("devices.id", ondelete="CASCADE"),
        nullable=False,
    )
    command_type: Mapped[str] = mapped_column(String(80), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="queued")
    result: Mapped[dict | None] = mapped_column(JSONB)
    created_by: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    picked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(40), nullable=False, default="api")
    idempotency_key: Mapped[str | None] = mapped_column(String(128))


class TerminalSession(Base):
    __tablename__ = "terminal_sessions"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    device_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("devices.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    command_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("device_commands.id", ondelete="SET NULL"),
    )
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="queued")
    columns: Mapped[int] = mapped_column(Integer, nullable=False, default=80)
    rows: Mapped[int] = mapped_column(Integer, nullable=False, default=24)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    last_activity_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    connected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    close_reason: Mapped[str | None] = mapped_column(Text)


class TerminalFrame(Base):
    __tablename__ = "terminal_frames"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    session_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("terminal_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    direction: Mapped[str] = mapped_column(String(8), nullable=False)
    frame_type: Mapped[str] = mapped_column(String(16), nullable=False)
    payload: Mapped[bytes | None] = mapped_column(LargeBinary)
    frame_data: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


class ClientProfile(Base):
    __tablename__ = "client_profiles"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    device_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("devices.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    policy: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    __table_args__ = (
        UniqueConstraint("device_id", "name", name="uq_client_profiles_device_name"),
    )


class NetworkClient(Base):
    __tablename__ = "network_clients"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    device_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("devices.id", ondelete="CASCADE"),
        nullable=False,
    )
    profile_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("client_profiles.id", ondelete="SET NULL")
    )
    mac: Mapped[str] = mapped_column(String(17), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(120))
    vendor: Mapped[str | None] = mapped_column(String(160))
    hostname: Mapped[str | None] = mapped_column(String(120))
    ip_address: Mapped[str | None] = mapped_column(String(45))
    interface: Mapped[str | None] = mapped_column(String(80))
    online: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    presence_state: Mapped[str] = mapped_column(
        String(20), nullable=False, default="offline"
    )
    presence_source: Mapped[str | None] = mapped_column(String(40))
    last_observed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    online_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    presence_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    is_static: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    policy: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    __table_args__ = (
        UniqueConstraint("device_id", "mac", name="uq_network_clients_device_mac"),
    )


class ClientTrafficSample(Base):
    __tablename__ = "client_traffic_samples"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    client_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("network_clients.id", ondelete="CASCADE"),
        nullable=False,
    )
    rx_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    tx_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    user_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    action: Mapped[str] = mapped_column(String(120), nullable=False)
    object_type: Mapped[str | None] = mapped_column(String(80))
    object_id: Mapped[str | None] = mapped_column(String(120))
    details: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


class EventRecord(Base):
    __tablename__ = "event_records"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    device_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("devices.id", ondelete="CASCADE")
    )
    event_type: Mapped[str] = mapped_column(String(120), nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False, default="info")
    source: Mapped[str] = mapped_column(String(40), nullable=False, default="server")
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False, default="")
    event_data: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    fingerprint: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="open")
    occurrence_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    last_occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    snoozed_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class NotificationRule(Base):
    __tablename__ = "notification_rules"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    device_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("devices.id", ondelete="CASCADE")
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    event_types: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    severities: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    channels: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    quiet_hours: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    notify_recovery: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


class AutomationRule(Base):
    __tablename__ = "automation_rules"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    device_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("devices.id", ondelete="CASCADE")
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    trigger_type: Mapped[str] = mapped_column(String(120), nullable=False)
    conditions: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    action_command: Mapped[str] = mapped_column(String(80), nullable=False)
    action_payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    cooldown_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=300)
    max_runs_per_hour: Mapped[int] = mapped_column(Integer, nullable=False, default=6)
    dry_run: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    allow_disruptive: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    last_triggered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


class AutomationRun(Base):
    __tablename__ = "automation_runs"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    rule_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("automation_rules.id", ondelete="CASCADE"),
        nullable=False,
    )
    event_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("event_records.id", ondelete="SET NULL")
    )
    command_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("device_commands.id", ondelete="SET NULL")
    )
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


Index("ix_devices_status", Device.status)
Index("ix_user_sessions_user_revoked", UserSession.user_id, UserSession.revoked_at)
Index(
    "ix_mobile_pairing_tokens_user_created",
    MobilePairingToken.user_id,
    MobilePairingToken.created_at.desc(),
)
Index(
    "ix_mobile_pairing_attempts_identity_created",
    MobilePairingAttempt.identity_hash,
    MobilePairingAttempt.created_at.desc(),
)
Index(
    "ix_mobile_pairing_attempts_token_created",
    MobilePairingAttempt.token_hash,
    MobilePairingAttempt.created_at.desc(),
)
Index("ix_mobile_pairing_attempts_created", MobilePairingAttempt.created_at)
Index(
    "ix_auth_attempts_identity_created",
    AuthAttempt.identity_hash,
    AuthAttempt.created_at,
)
Index("ix_auth_attempts_ip_created", AuthAttempt.ip_hash, AuthAttempt.created_at)
Index("ix_devices_previous_token_hash", Device.previous_token_hash)
Index(
    "ix_device_telemetry_device_created",
    DeviceTelemetry.device_id,
    DeviceTelemetry.created_at.desc(),
)
Index(
    "ix_device_telemetry_metrics_device_created",
    DeviceTelemetryMetric.device_id,
    DeviceTelemetryMetric.created_at.desc(),
)
Index("ix_device_commands_device_status", DeviceCommand.device_id, DeviceCommand.status)
Index(
    "uq_device_commands_device_idempotency",
    DeviceCommand.device_id,
    DeviceCommand.idempotency_key,
    unique=True,
    postgresql_where=DeviceCommand.idempotency_key.is_not(None),
)
Index(
    "ix_terminal_sessions_device_status",
    TerminalSession.device_id,
    TerminalSession.status,
)
Index(
    "ix_terminal_frames_session_direction_id",
    TerminalFrame.session_id,
    TerminalFrame.direction,
    TerminalFrame.id,
)
Index("ix_network_clients_device_online", NetworkClient.device_id, NetworkClient.online)
Index(
    "ix_network_clients_device_presence",
    NetworkClient.device_id,
    NetworkClient.presence_state,
)
Index(
    "ix_client_traffic_client_created",
    ClientTrafficSample.client_id,
    ClientTrafficSample.created_at,
)
Index("ix_audit_log_created", AuditLog.created_at.desc())
Index(
    "ix_event_records_device_occurred",
    EventRecord.device_id,
    EventRecord.occurred_at.desc(),
)
Index("ix_event_records_type_status", EventRecord.event_type, EventRecord.status)
Index(
    "ix_event_records_fingerprint_last",
    EventRecord.fingerprint,
    EventRecord.last_occurred_at.desc(),
)
Index(
    "ix_notification_rules_device_enabled",
    NotificationRule.device_id,
    NotificationRule.enabled,
)
Index(
    "ix_automation_rules_trigger_enabled",
    AutomationRule.trigger_type,
    AutomationRule.enabled,
)
Index(
    "ix_automation_runs_rule_created",
    AutomationRun.rule_id,
    AutomationRun.created_at.desc(),
)
