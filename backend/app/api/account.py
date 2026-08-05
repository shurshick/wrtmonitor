from datetime import datetime
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select, desc
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import AuditLog, UserSession, PushToken, User
from ..services.auth import current_user


router = APIRouter(tags=["account"])


class AuditLogResponse(BaseModel):
    id: UUID
    action: str
    object_type: str | None = None
    object_id: str | None = None
    details: dict | None = None
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class SessionResponse(BaseModel):
    id: UUID
    client_type: str
    client_name: str | None = None
    client_version: str | None = None
    ip_address: str | None = None
    created_at: datetime
    last_used_at: datetime | None = None
    expires_at: datetime
    revoked_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class RegisterPushTokenRequest(BaseModel):
    token: str
    device_type: str = "android"


@router.get("/account/audit", response_model=list[AuditLogResponse])
def get_audit_logs(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    stmt = (
        select(AuditLog)
        .where(AuditLog.user_id == current_user.id)
        .order_by(desc(AuditLog.created_at))
        .offset(offset)
        .limit(limit)
    )
    return list(db.scalars(stmt))


@router.get("/account/sessions", response_model=list[SessionResponse])
def get_sessions(
    current_user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    stmt = (
        select(UserSession)
        .where(UserSession.user_id == current_user.id)
        .order_by(desc(UserSession.last_used_at.nulls_last()), desc(UserSession.created_at))
    )
    return list(db.scalars(stmt))


@router.post("/account/sessions/{session_id}/revoke")
def revoke_session(
    session_id: UUID,
    current_user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    session = db.get(UserSession, session_id)
    if not session or session.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Session not found")
    
    if not session.revoked_at:
        session.revoked_at = datetime.now()
        db.commit()
    
    return {"status": "ok"}


@router.post("/account/push-tokens")
def register_push_token(
    request: RegisterPushTokenRequest,
    current_user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    stmt = select(PushToken).where(PushToken.token == request.token)
    existing = db.scalar(stmt)
    
    if existing:
        if existing.user_id != current_user.id:
            # Token transferred to another user?
            existing.user_id = current_user.id
            existing.updated_at = datetime.now()
            db.commit()
    else:
        new_token = PushToken(
            user_id=current_user.id,
            token=request.token,
            device_type=request.device_type,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
        db.add(new_token)
        db.commit()

    return {"status": "ok"}
