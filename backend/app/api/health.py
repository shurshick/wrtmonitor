from typing import Any

from fastapi import APIRouter, Depends, Response

from ..config import ACCESS_MODEL, Settings, load_settings
from ..db import check_database
from ..contracts import (
    COMMAND_CONTRACT_VERSION,
    TELEMETRY_SCHEMA_CURRENT,
    TELEMETRY_SCHEMA_SUPPORTED,
)
from ..observability import prometheus_metrics
from ..services.commands import ALLOWED_COMMANDS
from ..services.openwrt_downloads import openwrt_download_metadata


router = APIRouter()


def settings() -> Settings:
    return load_settings()


@router.get("/health")
def health() -> dict[str, str]:
    check_database()
    return {"status": "ok", "database": "postgresql"}


@router.get("/live")
def liveness() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/ready")
def readiness() -> dict[str, str]:
    check_database()
    return {"status": "ready", "database": "postgresql"}


@router.get("/metrics", include_in_schema=False)
def metrics(config: Settings = Depends(settings)) -> Response:
    if not config.enable_metrics:
        return Response(status_code=404)
    return Response(prometheus_metrics(), media_type="text/plain; version=0.0.4")


@router.get("/api/v1/meta/contracts")
def contracts() -> dict:
    return {
        "command_contract_version": COMMAND_CONTRACT_VERSION,
        "telemetry_schema_current": TELEMETRY_SCHEMA_CURRENT,
        "telemetry_schema_supported": sorted(TELEMETRY_SCHEMA_SUPPORTED),
        "command_count": len(ALLOWED_COMMANDS),
    }


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
