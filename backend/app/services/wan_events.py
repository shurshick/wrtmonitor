from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from .audit import audit
from .telemetry import normalize_network_summary


def _mwan_state(payload: dict[str, Any] | None) -> dict[str, Any]:
    network = normalize_network_summary(payload or {})
    mwan = network.get("mwan3") or {}
    return {
        "enabled": bool(mwan.get("enabled")),
        "service": str(mwan.get("service") or "unavailable"),
        "status": " ".join(str(mwan.get("status") or "").split()),
        "members": [
            {
                "role": str(item.get("role") or ""),
                "interface": str(item.get("interface") or ""),
                "metric": item.get("metric"),
            }
            for item in mwan.get("members") or []
            if isinstance(item, dict)
        ],
    }


def record_wan_transition(
    db: Session,
    device_id: UUID,
    previous: dict[str, Any] | None,
    current: dict[str, Any],
) -> None:
    before = _mwan_state(previous)
    after = _mwan_state(current)
    if before == after or (not before["status"] and not after["status"]):
        return
    audit(
        db,
        None,
        "wan.failover",
        "device",
        str(device_id),
        {"before": before, "after": after},
    )


__all__ = ["record_wan_transition"]
