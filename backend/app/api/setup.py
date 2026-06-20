from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..config import Settings
from ..db import get_db
from ..services.auth import settings
from ..services.setup import (
    complete_setup,
    get_public_server_url,
    has_admin,
    is_setup_required,
)
from ..schemas import SetupRequest


router = APIRouter(prefix="/api/v1/setup")


@router.get("/status")
def setup_status(
    config: Settings = Depends(settings), db: Session = Depends(get_db)
) -> dict[str, Any]:
    return {
        "setup_required": is_setup_required(db, config),
        "admin_exists": has_admin(db),
        "server_url": get_public_server_url(db, config),
    }


@router.post("/complete")
def setup_complete(
    payload: SetupRequest,
    config: Settings = Depends(settings),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    return complete_setup(payload, config, db)
