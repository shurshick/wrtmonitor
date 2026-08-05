from fastapi import APIRouter, BackgroundTasks, Query
from .route_shared import (
    APP_NAME,
    APP_VERSION,
    Cookie,
    Depends,
    Device,
    Form,
    HTMLResponse,
    RedirectResponse,
    Request,
    Session,
    Settings,
    User,
    audit,
    create_web_session_token,
    enforce_login_rate_limit,
    generate_csrf_token,
    get_db,
    is_setup_required,
    operational_notifications,
    record_login_attempt,
    request_uses_https,
    require_web_csrf,
    select,
    settings,
    templates,
    verify_user_password,
    web_user_from_session,
)

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
def index(
    request: Request,
    config: Settings = Depends(settings),
    db: Session = Depends(get_db),
    wrtmonitor_session: str | None = Cookie(default=None),
):
    if is_setup_required(db, config):
        return RedirectResponse("/setup", status_code=303)
    user = web_user_from_session(wrtmonitor_session, config, db)
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "app_name": APP_NAME,
            "version": APP_VERSION,
            "authenticated": bool(user),
            "api_docs_enabled": config.enable_api_docs,
        },
    )


@router.get("/login", response_class=HTMLResponse)
def login_page(
    request: Request,
    reason: str | None = None,
    next: str | None = None,
    config: Settings = Depends(settings),
    db: Session = Depends(get_db),
):
    if is_setup_required(db, config):
        return RedirectResponse("/setup", status_code=303)
    error = (
        "Браузер не сохранил защищённую сессию. Проверьте HTTPS и разрешение cookies."
        if reason == "session_cookie"
        else None
    )
    return templates.TemplateResponse(
        request,
        "login.html",
        {
            "error": error,
            "https_required": not config.allow_insecure_local
            and not request_uses_https(request),
            "public_server_url": config.public_server_url,
            "next": next or "",
        },
    )


def _send_login_push_task(user_id, request_host):
    from ..services.fcm import send_push_notification
    from ..db import get_engine
    
    with Session(get_engine()) as session:
        send_push_notification(
            session,
            user_id,
            "Новый вход",
            f"Выполнен вход с IP: {request_host or 'неизвестно'}",
            {"type": "login", "ip": request_host or ""}
        )


@router.post("/login")
def login_form(
    request: Request,
    background_tasks: BackgroundTasks,
    username: str = Form(...),
    password: str = Form(...),
    config: Settings = Depends(settings),
    db: Session = Depends(get_db),
    next: str | None = Query(None),
):
    if is_setup_required(db, config):
        return RedirectResponse("/setup", status_code=303)
    if not config.allow_insecure_local and not request_uses_https(request):
        return templates.TemplateResponse(
            request,
            "login.html",
            {
                "error": "Вход через HTTP отключён: браузер не сохранит защищённую сессию.",
                "https_required": True,
                "public_server_url": config.public_server_url,
            },
            status_code=400,
        )
    username = username.strip()
    request_host = request.client.host if request.client else None
    try:
        enforce_login_rate_limit(db, config, username, request_host)
    except PermissionError:
        return templates.TemplateResponse(
            request,
            "message.html",
            {
                "title": "Вход временно ограничен",
                "message": "Слишком много неудачных попыток. Повторите вход позднее.",
                "link": "/login",
            },
            status_code=429,
        )
    user = db.scalars(
        select(User).where(User.username == username, User.disabled.is_(False))
    ).first()
    if not verify_user_password(password, user.password_hash if user else None):
        record_login_attempt(db, config, username, request_host, accepted=False)
        db.commit()
        return templates.TemplateResponse(
            request,
            "message.html",
            {
                "title": "Вход не выполнен",
                "message": "Проверьте логин и пароль.",
                "link": "/login",
            },
            status_code=401,
        )
    record_login_attempt(db, config, username, request_host, accepted=True)
    background_tasks.add_task(_send_login_push_task, user.id, request_host)

    response = RedirectResponse("/devices?login=1", status_code=303)
    response.set_cookie(
        "wrtmonitor_session",
        create_web_session_token(user.id, user.role, config),
        httponly=True,
        secure=not config.allow_insecure_local,
        samesite="lax",
        max_age=8 * 60 * 60,
    )
    audit(db, user.id, "auth.web_login", "user", str(user.id))
    db.commit()
    return response


@router.post("/logout")
def logout_form(
    csrf_token: str = Form(...),
    config: Settings = Depends(settings),
    db: Session = Depends(get_db),
    wrtmonitor_session: str | None = Cookie(default=None),
) -> RedirectResponse:
    require_web_csrf(wrtmonitor_session, csrf_token, config)
    user = web_user_from_session(wrtmonitor_session, config, db)
    if user:
        audit(db, user.id, "auth.web_logout", "user", str(user.id))
        db.commit()
    response = RedirectResponse("/", status_code=303)
    response.delete_cookie("wrtmonitor_session")
    return response


@router.get("/devices", response_class=HTMLResponse)
def devices_page(
    request: Request,
    login: bool = False,
    config: Settings = Depends(settings),
    db: Session = Depends(get_db),
    wrtmonitor_session: str | None = Cookie(default=None),
):
    if is_setup_required(db, config):
        return RedirectResponse("/setup", status_code=303)
    user = web_user_from_session(wrtmonitor_session, config, db)
    if not user:
        target = "/login?reason=session_cookie" if login else "/login"
        return RedirectResponse(target, status_code=303)
    if login:
        return RedirectResponse("/devices", status_code=303)
    csrf_token = generate_csrf_token(wrtmonitor_session or "", config.jwt_secret)
    devices = db.scalars(
        select(Device)
        .where(Device.archived_at.is_(None))
        .order_by(Device.created_at.desc())
    ).all()
    return templates.TemplateResponse(
        request,
        "devices.html",
        {
            "devices": devices,
            "csrf_token": csrf_token,
            "notifications_count": len(operational_notifications(db)),
        },
    )


__all__ = ["router", "index", "login_page", "login_form", "logout_form", "devices_page"]
