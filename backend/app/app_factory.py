from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .config import APP_NAME, APP_VERSION, load_settings
from .db import check_database, init_db
from .web.security_headers import SecurityHeadersMiddleware


def create_app() -> FastAPI:
    settings = load_settings()
    app = FastAPI(
        title=APP_NAME,
        version=APP_VERSION,
        docs_url="/docs" if settings.enable_api_docs else None,
        redoc_url="/redoc" if settings.enable_api_docs else None,
        openapi_url="/openapi.json" if settings.enable_api_docs else None,
    )
    app.add_middleware(SecurityHeadersMiddleware)
    app.mount("/static", StaticFiles(directory="backend/app/static"), name="static")

    @app.on_event("startup")
    def startup() -> None:
        init_db()
        check_database()

    return app


app = create_app()


def register_routers() -> None:
    # Import after app creation so decorator-based compatibility routes can attach.
    from .web import routes  # noqa: F401
    from .api.health import router as health_router
    from .api.auth import router as auth_router
    from .api.setup import router as setup_router
    from .api.devices import router as devices_router
    from .api.telemetry import router as telemetry_router
    from .api.commands import router as commands_router
    from .api.agent import router as agent_router

    app.include_router(health_router)
    app.include_router(auth_router)
    app.include_router(setup_router)
    app.include_router(devices_router)
    app.include_router(telemetry_router)
    app.include_router(commands_router)
    app.include_router(agent_router)

