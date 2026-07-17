from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .config import APP_NAME, APP_VERSION, load_settings
from .db import check_database, init_db
from .services.openwrt_downloads import ensure_openwrt_download_metadata
from .web.security_headers import SecurityHeadersMiddleware


def create_app() -> FastAPI:
    settings = load_settings()

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        ensure_openwrt_download_metadata()
        init_db()
        check_database()
        yield

    app = FastAPI(
        title=APP_NAME,
        version=APP_VERSION,
        docs_url="/docs" if settings.enable_api_docs else None,
        redoc_url="/redoc" if settings.enable_api_docs else None,
        openapi_url="/openapi.json" if settings.enable_api_docs else None,
        lifespan=lifespan,
    )
    app.add_middleware(SecurityHeadersMiddleware)
    app.mount("/static", StaticFiles(directory="backend/app/static"), name="static")
    app.mount(
        "/downloads/openwrt",
        StaticFiles(directory="openwrt-agent"),
        name="openwrt-downloads",
    )

    return app


def register_routers(app: FastAPI) -> None:
    from .web.routes import router as web_router
    from .api.health import router as health_router
    from .api.auth import router as auth_router
    from .api.setup import router as setup_router
    from .api.devices import router as devices_router
    from .api.telemetry import router as telemetry_router
    from .api.commands import router as commands_router
    from .api.agent import router as agent_router
    from .api.clients import router as clients_router
    from .api.operations import router as operations_router

    app.include_router(web_router)
    app.include_router(health_router)
    app.include_router(auth_router)
    app.include_router(setup_router)
    app.include_router(devices_router)
    app.include_router(telemetry_router)
    app.include_router(commands_router)
    app.include_router(agent_router)
    app.include_router(clients_router)
    app.include_router(operations_router)


def create_application() -> FastAPI:
    app = create_app()
    register_routers(app)
    return app
