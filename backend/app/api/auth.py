from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import Settings
from ..db import get_db
from ..models import User
from ..services.auth import settings
from ..services.setup import is_setup_required
from ..schemas import LoginRequest
from ..security import create_access_token, verify_password


router = APIRouter(prefix="/api/v1/auth")


@router.post("/login")
def login(
    payload: LoginRequest,
    config: Settings = Depends(settings),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    if is_setup_required(db, config):
        raise HTTPException(status_code=403, detail="Setup required")
    user = db.scalars(
        select(User).where(User.username == payload.username, User.disabled.is_(False))
    ).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return {
        "access_token": create_access_token(user.id, user.role, config),
        "token_type": "bearer",
    }
