import secrets
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Device, User
from ..services.audit import audit
from ..services.auth import current_user
from ..services.devices import (
    archive_device_or_409,
    get_latest_agent_status,
    get_user_device_or_404,
)
from ..schemas import DeviceProvisionRequest
from ..security import hash_token


router = APIRouter(prefix="/api/v1/devices")


@router.get("")
def list_devices(
    _: User = Depends(current_user), db: Session = Depends(get_db)
) -> list[dict[str, Any]]:
    return [
        {
            "id": str(device.id),
            "name": device.name,
            "hostname": device.hostname,
            "model": device.model,
            "firmware": device.firmware,
            "status": device.status,
            "last_seen_at": device.last_seen_at.isoformat()
            if device.last_seen_at
            else None,
        }
        for device in db.scalars(
            select(Device)
            .where(Device.archived_at.is_(None))
            .order_by(Device.created_at.desc())
        ).all()
    ]


@router.post("/provision")
def provision_device(
    payload: DeviceProvisionRequest,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    device_token = secrets.token_urlsafe(32)
    now = datetime.now(UTC)
    device = db.scalars(
        select(Device)
        .where(
            Device.hostname == payload.hostname,
            Device.name == payload.name,
            Device.model == payload.model,
            Device.archived_at.is_(None),
        )
        .order_by(Device.updated_at.desc())
        .limit(1)
    ).first()
    if device:
        device.firmware, device.token_hash, device.status, device.updated_at = (
            payload.firmware,
            hash_token(device_token),
            "provisioned",
            now,
        )
    else:
        device = Device(
            id=uuid4(),
            name=payload.name,
            hostname=payload.hostname,
            model=payload.model,
            firmware=payload.firmware,
            token_hash=hash_token(device_token),
            status="provisioned",
            last_seen_at=None,
            created_at=now,
            updated_at=now,
        )
        db.add(device)
    audit(
        db,
        user.id,
        "device.provision",
        "device",
        str(device.id),
        {"hostname": payload.hostname},
    )
    db.commit()
    return {"device_id": str(device.id), "device_token": device_token}


@router.post("/{device_id}/archive")
def archive_device(
    device_id: UUID,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    device = get_user_device_or_404(db, user, device_id)
    archive_device_or_409(device)
    now = datetime.now(UTC)
    device.archived_at = now
    device.updated_at = now
    device.token_hash = hash_token(secrets.token_urlsafe(48))
    audit(
        db,
        user.id,
        "device.archive",
        "device",
        str(device.id),
        {"status": device.status},
    )
    db.commit()
    return {"status": "archived"}


@router.get("/{device_id}/agent")
def get_device_agent(
    device_id: UUID,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    get_user_device_or_404(db, user, device_id)
    return get_latest_agent_status(db, device_id)
