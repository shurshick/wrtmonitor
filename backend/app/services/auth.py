from datetime import UTC, datetime
from uuid import UUID

import jwt
from fastapi import Depends, Header, HTTPException
from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from ..config import Settings, load_settings
from ..db import get_db
from ..models import Device, User
from ..security import decode_access_token, hash_token


def settings() -> Settings:
    return load_settings()


def ensure_single_owner_access(user: User) -> User:
    if user.role != "owner":
        raise HTTPException(
            status_code=403,
            detail="This deployment supports only the owner account",
        )
    return user


def bearer_token(authorization: str | None) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Bearer token required")
    return authorization.removeprefix("Bearer ").strip()


def current_user(
    authorization: str | None = Header(default=None),
    config: Settings = Depends(settings),
    db: Session = Depends(get_db),
) -> User:
    token = bearer_token(authorization)
    try:
        payload = decode_access_token(token, config)
        user_id = UUID(str(payload.get("sub")))
    except (ValueError, jwt.PyJWTError) as exc:
        raise HTTPException(status_code=401, detail="Invalid access token") from exc
    user = db.get(User, user_id)
    if not user or user.disabled:
        raise HTTPException(status_code=401, detail="Invalid access token")
    return ensure_single_owner_access(user)


def device_from_token(
    authorization: str | None, db: Session, *, for_update: bool = False
) -> Device:
    token = bearer_token(authorization)
    token_hash = hash_token(token)
    query = select(Device).where(
        or_(
            Device.token_hash == token_hash,
            and_(
                Device.previous_token_hash == token_hash,
                Device.previous_token_expires_at > datetime.now(UTC),
            ),
        ),
        Device.archived_at.is_(None),
    )
    if for_update:
        query = query.with_for_update()
    device = db.scalars(query).first()
    if not device:
        raise HTTPException(status_code=401, detail="Invalid device token")
    return device


def web_user_from_session(
    session_token: str | None, config: Settings, db: Session
) -> User | None:
    if not session_token:
        return None
    try:
        payload = decode_access_token(session_token, config)
        user_id = UUID(str(payload.get("sub")))
    except (ValueError, jwt.PyJWTError):
        return None
    user = db.get(User, user_id)
    if not user or user.disabled:
        return None
    try:
        return ensure_single_owner_access(user)
    except HTTPException:
        return None
