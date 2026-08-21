from fastapi import APIRouter, Response
from uuid import uuid4
from ..config import APP_VERSION
from ..models import FeedbackRecord
from ..services.operations import build_server_diagnostic_archive
from .route_shared import (
    AuditLog,
    BACKUP_DIRECTORY,
    Cookie,
    Depends,
    FileResponse,
    Form,
    HTMLResponse,
    HTTPException,
    MobilePairingToken,
    Path,
    RedirectResponse,
    Request,
    Session,
    Settings,
    UTC,
    UUID,
    User,
    UserSession,
    audit,
    create_backup,
    create_pairing_token,
    datetime,
    default_backup_path,
    generate_csrf_token,
    get_db,
    get_public_server_url,
    get_user_pairing_token,
    hash_password,
    operational_notifications,
    pairing_response,
    pairing_status,
    require_web_csrf,
    revoke_all_user_sessions,
    segno,
    select,
    settings,
    templates,
    verify_password,
    web_user_from_session,
)

router = APIRouter()


@router.get("/account/diagnostics")
def web_server_diagnostics(
    config: Settings = Depends(settings),
    db: Session = Depends(get_db),
    wrtmonitor_session: str | None = Cookie(default=None),
) -> Response:
    user = web_user_from_session(wrtmonitor_session, config, db)
    if not user or user.role != "owner" or user.disabled:
        raise HTTPException(status_code=403, detail="Owner access required")
    return Response(
        build_server_diagnostic_archive(db, config),
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="wrtmonitor-server-{APP_VERSION}-diagnostics.zip"'
        },
    )


@router.get("/account", response_class=HTMLResponse)
def account_page(
    request: Request,
    config: Settings = Depends(settings),
    db: Session = Depends(get_db),
    wrtmonitor_session: str | None = Cookie(default=None),
):
    user = web_user_from_session(wrtmonitor_session, config, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    if user.role != "owner" or user.disabled:
        raise HTTPException(status_code=403, detail="Owner access required")
    return render_account_page(request, user, wrtmonitor_session or "", config, db)


def render_account_page(
    request: Request,
    user: User,
    session_token: str,
    config: Settings,
    db: Session,
    *,
    created_pairing: MobilePairingToken | None = None,
    pairing_qr_svg: str | None = None,
):
    sessions = db.scalars(
        select(UserSession)
        .where(UserSession.user_id == user.id)
        .order_by(UserSession.last_used_at.desc())
        .limit(100)
    ).all()
    audit_entries = db.scalars(
        select(AuditLog).order_by(AuditLog.created_at.desc()).limit(100)
    ).all()
    feedback_entries = db.scalars(
        select(FeedbackRecord)
        .where(FeedbackRecord.user_id == user.id)
        .order_by(FeedbackRecord.created_at.desc())
        .limit(10)
    ).all()
    backups = (
        sorted(BACKUP_DIRECTORY.glob("wrtmonitor-*.dump"), reverse=True)
        if BACKUP_DIRECTORY.is_dir()
        else []
    )
    public_server_url = get_public_server_url(db, config)
    latest_pairing = created_pairing or db.scalar(
        select(MobilePairingToken)
        .where(MobilePairingToken.user_id == user.id)
        .order_by(MobilePairingToken.created_at.desc())
        .limit(1)
    )
    response = templates.TemplateResponse(
        request,
        "account.html",
        {
            "user": user,
            "sessions": sessions,
            "audit_entries": audit_entries,
            "notifications": operational_notifications(db),
            "feedback_entries": feedback_entries,
            "feedback_sent": request.query_params.get("feedback") == "sent",
            "backups": backups,
            "pairing": pairing_response(latest_pairing) if latest_pairing else None,
            "pairing_qr_svg": pairing_qr_svg,
            "public_server_url": public_server_url,
            "csrf_token": generate_csrf_token(session_token, config.jwt_secret),
        },
    )
    response.headers["Cache-Control"] = "no-store"
    return response


@router.post("/account/feedback")
def web_create_feedback(
    category: str = Form(...),
    message: str = Form(...),
    csrf_token: str = Form(...),
    config: Settings = Depends(settings),
    db: Session = Depends(get_db),
    wrtmonitor_session: str | None = Cookie(default=None),
) -> RedirectResponse:
    require_web_csrf(wrtmonitor_session, csrf_token, config)
    user = web_user_from_session(wrtmonitor_session, config, db)
    if not user or user.disabled:
        raise HTTPException(status_code=401, detail="Требуется вход")
    clean_message = message.strip()
    if category not in {"bug", "idea", "usability", "other"}:
        raise HTTPException(status_code=422, detail="Неизвестная категория")
    if len(clean_message) < 10 or len(clean_message) > 4000:
        raise HTTPException(
            status_code=422, detail="Сообщение должно содержать от 10 до 4000 символов"
        )
    item = FeedbackRecord(
        id=uuid4(),
        user_id=user.id,
        device_id=None,
        source="web",
        category=category,
        message=clean_message,
        app_version=APP_VERSION,
        client_context={"screen": "account"},
        status="new",
        created_at=datetime.now(UTC),
    )
    db.add(item)
    audit(
        db, user.id, "feedback.create", "feedback", str(item.id), {"category": category}
    )
    db.commit()
    return RedirectResponse("/account?feedback=sent", status_code=303)


@router.post("/account/mobile-pairing", response_class=HTMLResponse)
def web_create_mobile_pairing(
    request: Request,
    csrf_token: str = Form(...),
    config: Settings = Depends(settings),
    db: Session = Depends(get_db),
    wrtmonitor_session: str | None = Cookie(default=None),
):
    require_web_csrf(wrtmonitor_session, csrf_token, config)
    user = web_user_from_session(wrtmonitor_session, config, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    if user.role != "owner" or user.disabled:
        raise HTTPException(status_code=403, detail="Owner access required")
    try:
        item, _, setup_payload = create_pairing_token(
            db, user, config, get_public_server_url(db, config)
        )
    except ValueError as exc:
        code = str(exc)
        status = 429 if code == "pairing_rate_limited" else 503
        raise HTTPException(status_code=status, detail=code) from exc
    audit(db, user.id, "mobile_pairing.token.created", "mobile_pairing", str(item.id))
    db.commit()
    qr_svg = segno.make(setup_payload, error="m").svg_inline(
        scale=5,
        dark="#07111f",
        light="#ffffff",
    )
    return render_account_page(
        request,
        user,
        wrtmonitor_session or "",
        config,
        db,
        created_pairing=item,
        pairing_qr_svg=qr_svg,
    )


@router.post("/account/mobile-pairing/{pairing_id}/revoke")
def web_revoke_mobile_pairing(
    pairing_id: UUID,
    csrf_token: str = Form(...),
    config: Settings = Depends(settings),
    db: Session = Depends(get_db),
    wrtmonitor_session: str | None = Cookie(default=None),
) -> RedirectResponse:
    require_web_csrf(wrtmonitor_session, csrf_token, config)
    user = web_user_from_session(wrtmonitor_session, config, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    if user.role != "owner" or user.disabled:
        raise HTTPException(status_code=403, detail="Owner access required")
    item = get_user_pairing_token(db, user.id, pairing_id)
    if not item:
        raise HTTPException(status_code=404, detail="QR-код не найден")
    if pairing_status(item) == "active":
        item.revoked_at = datetime.now(UTC)
        audit(
            db,
            user.id,
            "mobile_pairing.token.revoked",
            "mobile_pairing",
            str(item.id),
        )
        db.commit()
    return RedirectResponse("/account", status_code=303)


@router.post("/account/backups")
def web_create_database_backup(
    csrf_token: str = Form(...),
    config: Settings = Depends(settings),
    db: Session = Depends(get_db),
    wrtmonitor_session: str | None = Cookie(default=None),
) -> RedirectResponse:
    require_web_csrf(wrtmonitor_session, csrf_token, config)
    user = web_user_from_session(wrtmonitor_session, config, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    backup = create_backup(config.database_url, default_backup_path(BACKUP_DIRECTORY))
    audit(db, user.id, "database.backup.create", "backup", backup.name)
    db.commit()
    return RedirectResponse("/account", status_code=303)


@router.get("/account/backups/{filename}")
def web_download_database_backup(
    filename: str,
    config: Settings = Depends(settings),
    db: Session = Depends(get_db),
    wrtmonitor_session: str | None = Cookie(default=None),
) -> FileResponse:
    user = web_user_from_session(wrtmonitor_session, config, db)
    if not user:
        raise HTTPException(status_code=401, detail="Требуется вход")
    path = (BACKUP_DIRECTORY / Path(filename).name).resolve()
    if (
        path.parent != BACKUP_DIRECTORY.resolve()
        or not path.is_file()
        or path.suffix != ".dump"
    ):
        raise HTTPException(status_code=404, detail="Резервная копия не найдена")
    return FileResponse(path, filename=path.name, media_type="application/octet-stream")


@router.post("/account/password")
def web_change_password(
    current_password: str = Form(...),
    new_password: str = Form(...),
    new_password_confirm: str = Form(...),
    csrf_token: str = Form(...),
    config: Settings = Depends(settings),
    db: Session = Depends(get_db),
    wrtmonitor_session: str | None = Cookie(default=None),
) -> RedirectResponse:
    require_web_csrf(wrtmonitor_session, csrf_token, config)
    user = web_user_from_session(wrtmonitor_session, config, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    if not verify_password(current_password, user.password_hash):
        raise HTTPException(status_code=400, detail="Текущий пароль указан неверно")
    if len(new_password) < 12 or new_password != new_password_confirm:
        raise HTTPException(
            status_code=400,
            detail="Новый пароль должен содержать не менее 12 символов и совпадать с подтверждением",
        )
    if new_password == current_password:
        raise HTTPException(status_code=400, detail="Новый пароль должен отличаться")
    user.password_hash = hash_password(new_password)
    user.updated_at = datetime.now(UTC)
    revoke_all_user_sessions(db, user.id)
    audit(db, user.id, "auth.password.change", "user", str(user.id))
    db.commit()
    response = RedirectResponse("/login", status_code=303)
    response.delete_cookie("wrtmonitor_session")
    return response


@router.post("/account/sessions/{session_id}/revoke")
def web_revoke_session(
    session_id: UUID,
    csrf_token: str = Form(...),
    config: Settings = Depends(settings),
    db: Session = Depends(get_db),
    wrtmonitor_session: str | None = Cookie(default=None),
) -> RedirectResponse:
    require_web_csrf(wrtmonitor_session, csrf_token, config)
    user = web_user_from_session(wrtmonitor_session, config, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    session = db.get(UserSession, session_id)
    if not session or session.user_id != user.id:
        raise HTTPException(status_code=404, detail="Сессия не найдена")
    session.revoked_at = datetime.now(UTC)
    audit(db, user.id, "auth.session.revoke", "session", str(session.id))
    if session.client_type == "mobile_pairing":
        audit(
            db,
            user.id,
            "mobile_pairing.session.revoked",
            "session",
            str(session.id),
        )
    db.commit()
    return RedirectResponse("/account", status_code=303)


__all__ = [
    "router",
    "account_page",
    "render_account_page",
    "web_create_mobile_pairing",
    "web_create_feedback",
    "web_revoke_mobile_pairing",
    "web_create_database_backup",
    "web_download_database_backup",
    "web_change_password",
    "web_revoke_session",
]
