from fastapi import APIRouter
from .route_shared import (
    Cookie,
    Depends,
    Form,
    HTMLResponse,
    HTTPException,
    RedirectResponse,
    Request,
    Session,
    Settings,
    SetupRequest,
    complete_setup,
    generate_csrf_token,
    get_db,
    is_setup_required,
    secrets,
    settings,
    templates,
    verify_csrf_token,
)

router = APIRouter()


@router.get("/setup", response_class=HTMLResponse)
def setup_page(
    request: Request,
    config: Settings = Depends(settings),
    db: Session = Depends(get_db),
    wrtmonitor_setup_nonce: str | None = Cookie(default=None),
) -> HTMLResponse:
    if not is_setup_required(db, config):
        return templates.TemplateResponse(
            request,
            "message.html",
            {
                "title": "WrtMonitor настроен",
                "message": "Первичная настройка уже завершена.",
                "link": "/",
            },
        )
    nonce = wrtmonitor_setup_nonce or secrets.token_urlsafe(24)
    csrf_token = generate_csrf_token(nonce, config.jwt_secret)
    response = templates.TemplateResponse(
        request, "setup.html", {"csrf_token": csrf_token}
    )
    response.set_cookie(
        "wrtmonitor_setup_nonce",
        nonce,
        httponly=True,
        secure=not config.allow_insecure_local,
        samesite="lax",
        max_age=15 * 60,
    )
    return response


@router.post("/setup")
def setup_form(
    username: str = Form(...),
    password: str = Form(...),
    password_confirm: str = Form(...),
    server_url: str = Form(...),
    csrf_token: str = Form(...),
    config: Settings = Depends(settings),
    db: Session = Depends(get_db),
    wrtmonitor_setup_nonce: str | None = Cookie(default=None),
):
    if not wrtmonitor_setup_nonce or not verify_csrf_token(
        wrtmonitor_setup_nonce, csrf_token, config.jwt_secret
    ):
        raise HTTPException(status_code=403, detail="Invalid CSRF token")
    complete_setup(
        SetupRequest(
            username=username,
            password=password,
            password_confirm=password_confirm,
            server_url=server_url,
        ),
        config,
        db,
    )
    response = RedirectResponse("/", status_code=303)
    response.delete_cookie("wrtmonitor_setup_nonce")
    return response


__all__ = ["router", "setup_page", "setup_form"]
