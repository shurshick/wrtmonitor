import base64
from uuid import UUID

from fastapi import APIRouter, Cookie, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from ..config import Settings
from ..db import get_db
from ..services.audit import audit
from ..services.auth import settings, web_user_from_session
from ..services.command_store import create_device_command
from ..services.command_store import validate_command_request
from ..services.devices import device_supports, get_user_device_or_404
from ..services.setup import is_setup_required
from .csrf import require_web_csrf

router = APIRouter()


@router.post("/devices/{device_id}/backup/restore")
async def web_restore_router_backup(
    device_id: UUID,
    backup_file: UploadFile = File(...),
    csrf_token: str = Form(...),
    config: Settings = Depends(settings),
    db: Session = Depends(get_db),
    wrtmonitor_session: str | None = Cookie(default=None),
) -> RedirectResponse:
    if is_setup_required(db, config):
        return RedirectResponse("/setup", status_code=303)
    user = web_user_from_session(wrtmonitor_session, config, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    require_web_csrf(wrtmonitor_session, csrf_token, config)
    get_user_device_or_404(db, user, device_id)
    content = await backup_file.read(1_500_001)
    if len(content) > 1_500_000 or not content.startswith(b"\x1f\x8b"):
        raise HTTPException(status_code=400, detail="Invalid backup archive")
    payload = validate_command_request(
        command_type="maintenance.backup.restore",
        payload={"archive_base64": base64.b64encode(content).decode("ascii")},
        confirmed=True,
        device_supports=lambda capability: device_supports(db, device_id, capability),
    )
    command = create_device_command(
        db,
        device_id=device_id,
        command_type="maintenance.backup.restore",
        payload=payload,
        created_by=user.id,
        source="web",
    )
    audit(
        db,
        user.id,
        "command.create",
        "device_command",
        str(command.id),
        {
            "command_type": "maintenance.backup.restore",
            "source": "web",
            "confirmed": True,
        },
    )
    db.commit()
    return RedirectResponse(
        f"/devices/{device_id}?section=maintenance", status_code=303
    )


__all__ = ["router", "web_restore_router_backup"]
