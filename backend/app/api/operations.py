from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import User
from ..services.auth import current_user
from ..services.operations import operational_notifications


router = APIRouter(prefix="/api/v1/operations")


@router.get("/notifications")
def notifications(
    _: User = Depends(current_user), db: Session = Depends(get_db)
) -> list[dict]:
    return operational_notifications(db)
