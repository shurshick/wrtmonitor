from datetime import datetime
from uuid import UUID

from sqlalchemy import BigInteger, DateTime, Float, ForeignKey, Index, Integer
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from ..db import Base


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
    temperature_celsius: Mapped[float | None] = mapped_column(Float)
    storage_percent: Mapped[float | None] = mapped_column(Float)
    client_count: Mapped[int | None] = mapped_column(Integer)
    interfaces: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    wifi: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


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
