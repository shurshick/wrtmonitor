from uuid import UUID

import jwt
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import Settings
from ..db import get_db
from ..models import User, UserSession
from ..services.audit import audit
from ..services.auth import current_user, settings
from ..services.sessions import (
    create_user_session,
    revoke_all_user_sessions,
    rotate_user_session,
)
from ..services.setup import is_setup_required
from ..schemas import LoginRequest, PasswordChangeRequest, RefreshTokenRequest
from ..security import (
    create_access_token,
    decode_refresh_token,
    hash_password,
    verify_password,
)


router = APIRouter(prefix="/api/v1/auth")


@router.post("/login")
def login(
    request: Request,
    payload: LoginRequest,
    config: Settings = Depends(settings),
    db: Session = Depends(get_db),
) -> dict[str, str | int]:
    if is_setup_required(db, config):
        raise HTTPException(status_code=403, detail="Setup required")
    user = db.scalars(
        select(User).where(
            User.username == payload.username.strip(), User.disabled.is_(False)
        )
    ).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    _, refresh_token = create_user_session(
        db,
        user,
        config,
        client_name=request.headers.get("user-agent"),
        ip_address=request.client.host if request.client else None,
    )
    audit(db, user.id, "auth.login", "user", str(user.id))
    db.commit()
    return {
        "access_token": create_access_token(user.id, user.role, config),
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": 15 * 60,
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
        session_id = UUID(str(token_payload.get("jti")))
    except (ValueError, jwt.PyJWTError) as exc:
        raise HTTPException(status_code=401, detail="Invalid refresh token") from exc
    user = db.get(User, user_id)
    session = db.scalar(
        select(UserSession).where(UserSession.id == session_id).with_for_update()
    )
    if (
        not user
        or user.disabled
        or user.role != "owner"
        or not session
        or session.user_id != user.id
    ):
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    refresh_token = rotate_user_session(session, user, payload.refresh_token, config)
    if refresh_token is None:
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    db.commit()
    return {
        "access_token": create_access_token(user.id, user.role, config),
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": 15 * 60,
    }


@router.get("/sessions")
def list_sessions(
    user: User = Depends(current_user), db: Session = Depends(get_db)
) -> list[dict[str, str | None]]:
    sessions = db.scalars(
        select(UserSession)
        .where(UserSession.user_id == user.id)
        .order_by(UserSession.last_used_at.desc())
        .limit(100)
    ).all()
    return [
        {
            "id": str(item.id),
            "client_name": item.client_name,
            "ip_address": item.ip_address,
            "created_at": item.created_at.isoformat(),
            "last_used_at": item.last_used_at.isoformat(),
            "expires_at": item.expires_at.isoformat(),
            "revoked_at": item.revoked_at.isoformat() if item.revoked_at else None,
        }
        for item in sessions
    ]


@router.delete("/sessions/{session_id}")
def revoke_session(
    session_id: UUID,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    session = db.get(UserSession, session_id)
    if not session or session.user_id != user.id:
        raise HTTPException(status_code=404, detail="Session not found")
    session.revoked_at = datetime.now(UTC)
    audit(db, user.id, "auth.session.revoke", "session", str(session.id))
    db.commit()
    return {"status": "revoked"}


@router.post("/logout")
def logout_refresh_session(
    payload: RefreshTokenRequest,
    config: Settings = Depends(settings),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    try:
        token_payload = decode_refresh_token(payload.refresh_token, config)
        session_id = UUID(str(token_payload.get("jti")))
    except (ValueError, jwt.PyJWTError):
        return {"status": "logged_out"}
    session = db.get(UserSession, session_id)
    if session and session.revoked_at is None:
        session.revoked_at = datetime.now(UTC)
        db.commit()
    return {"status": "logged_out"}


@router.post("/change-password")
def change_password(
    payload: PasswordChangeRequest,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    if not verify_password(payload.current_password, user.password_hash):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    if payload.new_password != payload.new_password_confirm:
        raise HTTPException(status_code=400, detail="Passwords do not match")
    if payload.new_password == payload.current_password:
        raise HTTPException(status_code=400, detail="New password must be different")
    user.password_hash = hash_password(payload.new_password)
    user.updated_at = datetime.now(UTC)
    revoke_all_user_sessions(db, user.id)
    audit(db, user.id, "auth.password.change", "user", str(user.id))
    db.commit()
    return {"status": "password_changed"}
