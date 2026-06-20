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
    from . import routes  # noqa: F401
    from .api.health import router as health_router

    app.include_router(health_router)


register_routers()
