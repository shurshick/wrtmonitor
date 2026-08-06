from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import DeviceGroup, Device
from .dependencies import get_current_user_from_cookie, templates

router = APIRouter(tags=["web-fleet"])

@router.get("/fleet", response_class=HTMLResponse)
async def fleet_dashboard(
    request: Request,
    db: Session = Depends(get_db),
    user_session=Depends(get_current_user_from_cookie),
):
    groups = db.query(DeviceGroup).order_by(DeviceGroup.name).all()
    devices = db.query(Device).filter(Device.status != "disabled").order_by(Device.hostname).all()
    
    return templates.TemplateResponse(
        "fleet.html",
        {
            "request": request,
            "groups": groups,
            "devices": devices,
            "current_user": user_session.user if user_session else None,
        },
    )
