from typing import Any
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ..models import DeviceTelemetry


TELEMETRY_STALE_SECONDS = 5 * 60


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


def build_telemetry_summary(payload: dict[str, Any]) -> dict[str, Any]:
    system = payload.get("system") or {}
    memory = system.get("memory") or {}
    wifi = payload.get("wifi") or {}
    network = payload.get("network") or {}
    interfaces = network.get("interfaces") or network.get("interface") or []
    radios = wifi.get("radios") or []
    return {
        "uptime_seconds": system.get("uptime"),
        "load_1m": system.get("load"),
        "memory_total_mb": int(memory.get("total_kb", 0) or 0) // 1024,
        "memory_available_mb": int(
            memory.get("available_kb", memory.get("free_kb", 0)) or 0
        )
        // 1024,
        "wifi_available": bool(wifi.get("available", False)),
        "wifi_radio_count": len(radios),
        "network_interface_count": len(interfaces),
    }
