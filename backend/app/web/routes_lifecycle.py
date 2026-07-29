from fastapi import APIRouter
from .route_shared import (
    Cookie,
    Depends,
    Form,
    RedirectResponse,
    Session,
    Settings,
    UUID,
    audit,
    create_device_command,
    delete_device_permanently,
    get_db,
    get_user_device_or_404,
    is_setup_required,
    require_web_csrf,
    settings,
    web_user_from_session,
)

router = APIRouter()


@router.post("/devices/{device_id}/disconnect")
def disconnect_device_page(
    device_id: UUID,
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
    device = get_user_device_or_404(db, user, device_id)
    if device.status not in {"disabled", "disconnecting"}:
        command = create_device_command(
            db,
            device_id=device.id,
            command_type="agent.disconnect",
            payload={},
            created_by=user.id,
            source="web",
        )
        device.status = "disconnecting"
        audit(
            db,
            user.id,
            "device.disconnect",
            "device",
            str(device.id),
            {"command_id": str(command.id), "source": "web"},
        )
        db.commit()
    return RedirectResponse(f"/devices/{device_id}", status_code=303)


@router.post("/devices/{device_id}/delete")
@router.post("/devices/{device_id}/archive", deprecated=True)
def delete_device_page(
    device_id: UUID,
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
    device = get_user_device_or_404(db, user, device_id)
    delete_device_permanently(db, device)
    audit(
        db,
        user.id,
        "device.delete",
        None,
        None,
        {"source": "web"},
    )
    db.commit()
    return RedirectResponse("/devices", status_code=303)


__all__ = ["router", "disconnect_device_page", "delete_device_page"]
