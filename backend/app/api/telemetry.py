from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import DeviceTelemetry, User
from ..services.auth import current_user, device_from_token, settings
from ..services.devices import get_user_device_or_404
from ..services.telemetry import TELEMETRY_STALE_SECONDS, cleanup_device_telemetry
from ..schemas import TelemetryRequest
from ..services.telemetry import build_telemetry_summary


router = APIRouter()


@router.get("/api/v1/devices/{device_id}/telemetry/latest")
def latest_device_telemetry(
    device_id: UUID, user: User = Depends(current_user), db: Session = Depends(get_db)
) -> dict[str, Any]:
    get_user_device_or_404(db, user, device_id)
    telemetry = db.scalars(
        select(DeviceTelemetry)
        .where(DeviceTelemetry.device_id == device_id)
        .order_by(DeviceTelemetry.created_at.desc())
        .limit(1)
    ).first()
    if not telemetry:
        return {
            "device_id": str(device_id),
            "telemetry": None,
            "created_at": None,
            "age_seconds": None,
            "is_stale": False,
            "source": "agent",
            "summary": None,
        }
    age_seconds = max(
        0, int((datetime.now(UTC) - telemetry.created_at).total_seconds())
    )
    return {
        "device_id": str(device_id),
        "telemetry": telemetry.payload,
        "created_at": telemetry.created_at.isoformat(),
        "age_seconds": age_seconds,
        "is_stale": age_seconds > TELEMETRY_STALE_SECONDS,
        "source": "agent",
        "summary": build_telemetry_summary(telemetry.payload),
    }


@router.post("/api/v1/agent/telemetry")
def agent_telemetry(
    payload: TelemetryRequest,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    device = device_from_token(authorization, db)
    if device.id != payload.device_id:
        raise HTTPException(status_code=403, detail="Device token mismatch")
    now = datetime.now(UTC)
    device.status, device.last_seen_at, device.updated_at = "online", now, now
    db.add(
        DeviceTelemetry(
            id=uuid4(), device_id=device.id, payload=payload.telemetry, created_at=now
        )
    )
    db.flush()
    cleanup_device_telemetry(db, device.id, settings().telemetry_retention_per_device)
    db.commit()
    return {"status": "ok"}
