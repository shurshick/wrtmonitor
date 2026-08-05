from datetime import datetime, timezone
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select, desc
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import AuditLog, UserSession, User
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
    ip_address: str | None = None
    user_agent: str | None = None
    created_at: datetime
    expires_at: datetime
    revoked_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


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
        .order_by(desc(UserSession.created_at))
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
        raise HTTPException(status_code=404, detail="Сессия не найдена")

    if session.revoked_at is None:
        session.revoked_at = datetime.now(timezone.utc)
        db.commit()

    return {"status": "ok"}
