import asyncio
import base64
import binascii
from io import BytesIO
from uuid import UUID

import segno
from fastapi import APIRouter, Cookie, Depends, Form, HTTPException
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import Settings
from ..db import get_db
from ..models import DeviceCommand
from ..services.auth import settings, web_user_from_session
from ..services.command_store import create_device_command
from ..services.command_store import validate_command_request
from ..services.devices import device_supports, get_user_device_or_404
from ..services.wifi_qr_broker import consume_wifi_qr_result
from .csrf import require_web_csrf

router = APIRouter()


@router.post("/devices/{device_id}/wifi-qr.svg")
async def web_wifi_qr(
    device_id: UUID,
    iface: str = Form(...),
    csrf_token: str = Form(...),
    config: Settings = Depends(settings),
    db: Session = Depends(get_db),
    wrtmonitor_session: str | None = Cookie(default=None),
) -> Response:
    user = web_user_from_session(wrtmonitor_session, config, db)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    require_web_csrf(wrtmonitor_session, csrf_token, config)
    get_user_device_or_404(db, user, device_id)
    payload = validate_command_request(
        command_type="wifi.get_qr",
        payload={"iface": iface},
        confirmed=True,
        device_supports=lambda capability: device_supports(db, device_id, capability),
    )
    command = create_device_command(
        db,
        device_id=device_id,
        command_type="wifi.get_qr",
        payload=payload,
        created_by=user.id,
        source="web",
    )
    db.commit()
    for _ in range(120):
        result = consume_wifi_qr_result(command.id)
        if result is not None:
            wifi_uri = result.get("wifi_uri")
            if not isinstance(wifi_uri, str) or not wifi_uri.startswith("WIFI:"):
                raise HTTPException(
                    status_code=422,
                    detail=str(result.get("error") or "Wi-Fi QR is unavailable"),
                )
            image = BytesIO()
            segno.make(wifi_uri, error="m").save(
                image, kind="svg", scale=7, border=2, xmldecl=False
            )
            return Response(
                content=image.getvalue(),
                media_type="image/svg+xml",
                headers={"Cache-Control": "no-store, private"},
            )
        await asyncio.sleep(0.25)
    raise HTTPException(status_code=504, detail="Router did not return Wi-Fi QR")


@router.get("/devices/{device_id}/commands/{command_id}/download/{kind}")
def download_command_artifact(
    device_id: UUID,
    command_id: UUID,
    kind: str,
    config: Settings = Depends(settings),
    db: Session = Depends(get_db),
    wrtmonitor_session: str | None = Cookie(default=None),
) -> Response:
    user = web_user_from_session(wrtmonitor_session, config, db)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    get_user_device_or_404(db, user, device_id)
    command = db.scalar(
        select(DeviceCommand).where(
            DeviceCommand.id == command_id,
            DeviceCommand.device_id == device_id,
            DeviceCommand.status == "success",
        )
    )
    if command is None or not isinstance(command.result, dict):
        raise HTTPException(status_code=404, detail="Artifact not found")
    field, filename = {
        "backup": ("archive_base64", "wrtmonitor-openwrt-backup.tar.gz"),
        "diagnostics": ("bundle_base64", "wrtmonitor-diagnostics.tar.gz"),
    }.get(kind, ("", ""))
    encoded = command.result.get(field) if field else None
    if not isinstance(encoded, str):
        raise HTTPException(status_code=404, detail="Artifact not found")
    try:
        content = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise HTTPException(status_code=422, detail="Artifact is corrupted") from exc
    return Response(
        content=content,
        media_type="application/gzip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


__all__ = ["download_command_artifact", "router", "web_wifi_qr"]
