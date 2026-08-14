from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from ..db import Base


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
