import secrets
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import AuditLog, Device, User
from ..services.audit import audit
from ..services.auth import current_user
from ..services.devices import (
    delete_device_permanently,
    get_latest_agent_status,
    get_user_device_or_404,
    latest_device_telemetry,
)
from ..services.management_options import build_management_options
from ..services.firmware_catalog import firmware_catalog
from ..services.hardware_catalog import hardware_report
from ..services.telemetry import normalize_wifi_summary
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


def _delete_device(
    device_id: UUID,
    user: User,
    db: Session,
) -> dict[str, str]:
    device = get_user_device_or_404(db, user, device_id)
    delete_device_permanently(db, device)
    audit(
        db,
        user.id,
        "device.delete",
        None,
        None,
        {"source": "api"},
    )
    db.commit()
    return {"status": "deleted"}


@router.delete("/{device_id}")
def delete_device(
    device_id: UUID,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    return _delete_device(device_id, user, db)


@router.post("/{device_id}/archive", deprecated=True)
def delete_device_legacy(
    device_id: UUID,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    return _delete_device(device_id, user, db)


@router.get("/{device_id}/agent")
def get_device_agent(
    device_id: UUID,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    get_user_device_or_404(db, user, device_id)
    return get_latest_agent_status(db, device_id)


@router.get("/{device_id}/hardware/report")
def download_hardware_report(
    device_id: UUID,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> JSONResponse:
    device = get_user_device_or_404(db, user, device_id)
    telemetry = latest_device_telemetry(db, device_id)
    report = hardware_report(
        db, device_id, telemetry.payload if telemetry else {}, device
    )
    return JSONResponse(
        report,
        headers={
            "Content-Disposition": f'attachment; filename="wrtmonitor-hardware-{device_id}.json"'
        },
    )


@router.get("/{device_id}/management-options")
def get_device_management_options(
    device_id: UUID,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    get_user_device_or_404(db, user, device_id)
    telemetry = latest_device_telemetry(db, device_id)
    return build_management_options(telemetry.payload if telemetry else {})


@router.get("/{device_id}/wifi")
def get_device_wifi(
    device_id: UUID,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    get_user_device_or_404(db, user, device_id)
    telemetry = latest_device_telemetry(db, device_id)
    summary = normalize_wifi_summary(telemetry.payload if telemetry else {})
    return {
        "device_id": str(device_id),
        "observed_at": telemetry.created_at.isoformat() if telemetry else None,
        **summary,
    }


@router.get("/{device_id}/firmware-catalog")
def get_device_firmware_catalog(
    device_id: UUID,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    get_user_device_or_404(db, user, device_id)
    telemetry = latest_device_telemetry(db, device_id)
    return firmware_catalog(telemetry.payload if telemetry else {})


@router.get("/{device_id}/wan-events")
def get_device_wan_events(
    device_id: UUID,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    get_user_device_or_404(db, user, device_id)
    rows = db.scalars(
        select(AuditLog)
        .where(
            AuditLog.object_type == "device",
            AuditLog.object_id == str(device_id),
            AuditLog.action == "wan.failover",
        )
        .order_by(AuditLog.created_at.desc())
        .limit(50)
    ).all()
    return [
        {"created_at": row.created_at.isoformat(), "details": row.details or {}}
        for row in rows
    ]
