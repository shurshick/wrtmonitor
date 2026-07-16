from typing import Any

from fastapi import APIRouter, Depends

from ..config import ACCESS_MODEL, Settings, load_settings
from ..db import check_database
from ..services.openwrt_downloads import openwrt_download_metadata


router = APIRouter()


def settings() -> Settings:
    return load_settings()


@router.get("/health")
def health() -> dict[str, str]:
    check_database()
    return {"status": "ok", "database": "postgresql"}


@router.get("/health/config")
def health_config(config: Settings = Depends(settings)) -> dict[str, Any]:
    return {
        "status": "ok",
        "database_url_configured": bool(config.database_url),
        "jwt_secret_configured": bool(config.jwt_secret),
        "public_server_url_configured": bool(config.public_server_url),
        "api_docs_enabled": config.enable_api_docs,
        "access_model": ACCESS_MODEL,
        **openwrt_download_metadata(),
    }
