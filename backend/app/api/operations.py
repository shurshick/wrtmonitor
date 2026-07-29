from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import User
from ..services.auth import current_user
from ..config import APP_VERSION, load_settings
from ..services.operations import (
    build_server_diagnostic_archive,
    operation_metrics,
    operational_notifications,
)


router = APIRouter(prefix="/api/v1/operations")


@router.get("/notifications")
def notifications(
    _: User = Depends(current_user), db: Session = Depends(get_db)
) -> list[dict]:
    return operational_notifications(db)


@router.get("/metrics")
def metrics(_: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    return operation_metrics(db)


@router.get("/diagnostics/archive")
def diagnostic_archive(
    _: User = Depends(current_user), db: Session = Depends(get_db)
) -> StreamingResponse:
    config = load_settings()
    import io

    data = io.BytesIO(build_server_diagnostic_archive(db, config))
    return StreamingResponse(
        data,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="wrtmonitor-server-{APP_VERSION}-diagnostics.zip"'},
    )
