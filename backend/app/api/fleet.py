from uuid import UUID, uuid4
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session
from datetime import UTC, datetime

from ..db import get_db
from ..models import DeviceGroup, Device, User
from .auth import current_user
from ..schemas import CommandCreateRequest
from ..services.commands import (
    create_device_command,
    ALLOWED_COMMANDS,
    validate_command_request,
)
from ..services.devices import device_supports

router = APIRouter(prefix="/api/v1/fleet", tags=["fleet"])


class DeviceGroupCreate(BaseModel):
    name: str
    description: str | None = None


class DeviceGroupResponse(BaseModel):
    id: UUID
    name: str
    description: str | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DeviceGroupUpdate(BaseModel):
    name: str | None = None
    description: str | None = None


@router.get("/groups", response_model=list[DeviceGroupResponse])
def list_groups(db: Session = Depends(get_db), user: User = Depends(current_user)):
    return db.query(DeviceGroup).order_by(DeviceGroup.name).all()


@router.post("/groups", response_model=DeviceGroupResponse)
def create_group(
    group: DeviceGroupCreate,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    if db.query(DeviceGroup).filter_by(name=group.name).first():
        raise HTTPException(status_code=400, detail="Group name already exists")

    now = datetime.now(UTC)
    new_group = DeviceGroup(
        id=uuid4(),
        name=group.name.strip(),
        description=group.description,
        created_at=now,
        updated_at=now,
    )
    db.add(new_group)
    db.commit()
    db.refresh(new_group)
    return new_group


@router.put("/groups/{group_id}", response_model=DeviceGroupResponse)
def update_group(
    group_id: UUID,
    update_data: DeviceGroupUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    group = db.query(DeviceGroup).filter_by(id=group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    if update_data.name is not None:
        if (
            db.query(DeviceGroup)
            .filter_by(name=update_data.name)
            .filter(DeviceGroup.id != group_id)
            .first()
        ):
            raise HTTPException(status_code=400, detail="Group name already exists")
        group.name = update_data.name

    if update_data.description is not None:
        group.description = update_data.description

    group.updated_at = datetime.now(UTC)

    db.commit()
    db.refresh(group)
    return group


@router.delete("/groups/{group_id}")
def delete_group(
    group_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    group = db.query(DeviceGroup).filter_by(id=group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    db.delete(group)
    db.commit()
    return {"ok": True}


class DeviceAssign(BaseModel):
    device_ids: list[UUID]


@router.post("/groups/{group_id}/devices")
def assign_devices(
    group_id: UUID,
    payload: DeviceAssign,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    group = db.query(DeviceGroup).filter_by(id=group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    devices = db.query(Device).filter(Device.id.in_(payload.device_ids)).all()
    for device in devices:
        device.group_id = group.id

    db.commit()
    return {"assigned": len(devices)}


@router.delete("/groups/{group_id}/devices")
def remove_devices(
    group_id: UUID,
    payload: DeviceAssign,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    group = db.query(DeviceGroup).filter_by(id=group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    devices = (
        db.query(Device)
        .filter(Device.id.in_(payload.device_ids))
        .filter_by(group_id=group_id)
        .all()
    )
    for device in devices:
        device.group_id = None

    db.commit()
    return {"removed": len(devices)}


class FleetCommandResponse(BaseModel):
    command_ids: dict[UUID, str]
    skipped: dict[UUID, str]


@router.post("/groups/{group_id}/commands", response_model=FleetCommandResponse)
def create_group_command(
    group_id: UUID,
    payload: CommandCreateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    if payload.command_type not in ALLOWED_COMMANDS:
        raise HTTPException(status_code=400, detail="Command is not allowed")

    group = db.query(DeviceGroup).filter_by(id=group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    devices = db.query(Device).filter_by(group_id=group_id).all()
    if not devices:
        raise HTTPException(status_code=400, detail="No devices in group")

    command_ids: dict[UUID, str] = {}
    skipped: dict[UUID, str] = {}
    for device in devices:
        try:
            normalized_payload = validate_command_request(
                command_type=payload.command_type,
                payload=payload.payload,
                confirmed=payload.confirmed,
                device_supports=lambda capability, device_id=device.id: device_supports(
                    db, device_id, capability
                ),
            )
        except HTTPException as exc:
            skipped[device.id] = str(exc.detail)
            continue
        command = create_device_command(
            db,
            device_id=device.id,
            command_type=payload.command_type,
            payload=normalized_payload,
            created_by=user.id,
            source="fleet_api",
            idempotency_key=f"{payload.idempotency_key}_{device.id}"
            if payload.idempotency_key
            else None,
        )
        command_ids[device.id] = str(command.id)

    db.commit()
    return {"command_ids": command_ids, "skipped": skipped}
