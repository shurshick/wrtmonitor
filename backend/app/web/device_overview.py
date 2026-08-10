from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import EventRecord
from ..services.events import public_event


def daily_overview_context(
    db: Session, device_id: UUID, radios: list[dict[str, Any]]
) -> dict[str, Any]:
    interfaces = [
        interface
        for radio in radios
        for interface in (radio.get("interfaces") or [])
        if isinstance(interface, dict)
    ]
    primary = radios[0] if radios else {}
    guest = next(
        (
            item
            for item in interfaces
            if item.get("network") == "wrtmonitor_guest"
            or item.get("section") == "wrtmonitor_guest"
        ),
        {},
    )
    events = db.scalars(
        select(EventRecord)
        .where(EventRecord.device_id == device_id)
        .order_by(EventRecord.last_occurred_at.desc())
        .limit(5)
    ).all()
    return {
        "quick_wifi": {
            "available": bool(primary),
            "radio": str(primary.get("name") or primary.get("id") or ""),
            "enabled": not bool(primary.get("disabled", False)),
        },
        "quick_guest": {
            "configured": bool(guest),
            "enabled": bool(guest) and not bool(guest.get("disabled", False)),
            "radio": str(guest.get("device") or primary.get("name") or ""),
            "ssid": str(guest.get("ssid") or ""),
        },
        "recent_events": [public_event(item) for item in events],
    }


__all__ = ["daily_overview_context"]
