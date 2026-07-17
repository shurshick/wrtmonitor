from uuid import UUID

import jwt
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import Settings
from ..db import get_db
from ..models import User
from ..services.auth import settings
from ..services.setup import is_setup_required
from ..schemas import LoginRequest, RefreshTokenRequest
from ..security import (
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
    verify_password,
)


router = APIRouter(prefix="/api/v1/auth")


@router.post("/login")
def login(
    payload: LoginRequest,
    config: Settings = Depends(settings),
    db: Session = Depends(get_db),
) -> dict[str, str | int]:
    if is_setup_required(db, config):
        raise HTTPException(status_code=403, detail="Setup required")
    user = db.scalars(
        select(User).where(User.username == payload.username, User.disabled.is_(False))
    ).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return {
        "access_token": create_access_token(user.id, user.role, config),
        "refresh_token": create_refresh_token(user.id, user.role, config),
        "token_type": "bearer",
        "expires_in": 8 * 60 * 60,
    }


@router.post("/refresh")
def refresh_access_token(
    payload: RefreshTokenRequest,
    config: Settings = Depends(settings),
    db: Session = Depends(get_db),
) -> dict[str, str | int]:
    try:
        token_payload = decode_refresh_token(payload.refresh_token, config)
        user_id = UUID(str(token_payload.get("sub")))
    except (ValueError, jwt.PyJWTError) as exc:
        raise HTTPException(status_code=401, detail="Invalid refresh token") from exc
    user = db.get(User, user_id)
    if not user or user.disabled or user.role != "owner":
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    return {
        "access_token": create_access_token(user.id, user.role, config),
        "refresh_token": create_refresh_token(user.id, user.role, config),
        "token_type": "bearer",
        "expires_in": 8 * 60 * 60,
    }
