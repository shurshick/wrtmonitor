from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import delete, or_, update
from sqlalchemy.orm import Session

from ..config import Settings
from ..models import User, UserSession
from ..security import create_refresh_token, hash_token


def create_user_session(
    db: Session,
    user: User,
    config: Settings,
    *,
    client_name: str | None = None,
    ip_address: str | None = None,
    client_type: str = "password",
) -> tuple[UserSession, str]:
    now = datetime.now(UTC)
    db.execute(
        delete(UserSession).where(
            UserSession.user_id == user.id,
            or_(
                UserSession.expires_at < now,
                UserSession.revoked_at < now - timedelta(days=30),
            ),
        )
    )
    session = UserSession(
        id=uuid4(),
        user_id=user.id,
        refresh_token_hash="pending",
        client_type=client_type,
        client_name=(client_name or "Unknown client")[:160],
        ip_address=(ip_address or "")[:64] or None,
        created_at=now,
        last_used_at=now,
        expires_at=now + timedelta(days=30),
        revoked_at=None,
    )
    token = create_refresh_token(user.id, user.role, session.id, config)
    session.refresh_token_hash = hash_token(token)
    db.add(session)
    return session, token


def rotate_user_session(
    session: UserSession, user: User, presented_token: str, config: Settings
) -> str | None:
    now = datetime.now(UTC)
    if (
        session.revoked_at is not None
        or session.expires_at <= now
        or session.refresh_token_hash != hash_token(presented_token)
    ):
        return None
    token = create_refresh_token(user.id, user.role, session.id, config)
    session.refresh_token_hash = hash_token(token)
    session.last_used_at = now
    return token


def revoke_all_user_sessions(db: Session, user_id: UUID) -> None:
    db.execute(
        update(UserSession)
        .where(UserSession.user_id == user_id, UserSession.revoked_at.is_(None))
        .values(revoked_at=datetime.now(UTC))
    )
