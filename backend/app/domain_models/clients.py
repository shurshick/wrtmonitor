from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from ..db import Base


class ClientProfile(Base):
    __tablename__ = "client_profiles"
    __table_args__ = (
        UniqueConstraint("device_id", "name", name="uq_client_profiles_device_name"),
    )

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


class NetworkClient(Base):
    __tablename__ = "network_clients"
    __table_args__ = (
        UniqueConstraint("device_id", "mac", name="uq_network_clients_device_mac"),
    )

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
    device_type: Mapped[str] = mapped_column(
        String(24), nullable=False, default="unknown"
    )
    device_type_source: Mapped[str] = mapped_column(
        String(16), nullable=False, default="automatic"
    )
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


class ClientActivityEvent(Base):
    __tablename__ = "client_activity_events"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    client_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("network_clients.id", ondelete="CASCADE"),
        nullable=False,
    )
    state: Mapped[str] = mapped_column(String(20), nullable=False)
    source: Mapped[str | None] = mapped_column(String(40))
    ip_address: Mapped[str | None] = mapped_column(String(45))
    interface: Mapped[str | None] = mapped_column(String(80))
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
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
Index(
    "ix_client_activity_client_occurred",
    ClientActivityEvent.client_id,
    ClientActivityEvent.occurred_at.desc(),
)
