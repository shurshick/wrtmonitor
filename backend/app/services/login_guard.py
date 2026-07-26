from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import delete, func, or_, select
from sqlalchemy.orm import Session

from ..config import Settings
from ..models import AuthAttempt
from ..security import hash_token


def _digest(config: Settings, kind: str, value: str) -> str:
    return hash_token(f"{config.jwt_secret}\0{kind}\0{value.strip().lower()}")


def login_identity(request_host: str | None, username: str) -> tuple[str, str]:
    return username.strip().lower(), (request_host or "unknown").strip().lower()


def enforce_login_rate_limit(
    db: Session,
    config: Settings,
    username: str,
    request_host: str | None,
) -> None:
    identity, address = login_identity(request_host, username)
    identity_hash = _digest(config, "identity", identity)
    ip_hash = _digest(config, "ip", address)
    cutoff = datetime.now(UTC) - timedelta(
        seconds=config.login_rate_limit_window_seconds
    )
    failures = db.scalar(
        select(func.count(AuthAttempt.id)).where(
            AuthAttempt.accepted.is_(False),
            AuthAttempt.created_at >= cutoff,
            or_(
                AuthAttempt.identity_hash == identity_hash,
                AuthAttempt.ip_hash == ip_hash,
            ),
        )
    )
    if int(failures or 0) >= config.login_rate_limit_attempts:
        raise PermissionError("login_rate_limited")


def record_login_attempt(
    db: Session,
    config: Settings,
    username: str,
    request_host: str | None,
    *,
    accepted: bool,
) -> None:
    identity, address = login_identity(request_host, username)
    now = datetime.now(UTC)
    identity_hash = _digest(config, "identity", identity)
    ip_hash = _digest(config, "ip", address)
    if accepted:
        db.execute(
            delete(AuthAttempt).where(
                AuthAttempt.accepted.is_(False),
                or_(
                    AuthAttempt.identity_hash == identity_hash,
                    AuthAttempt.ip_hash == ip_hash,
                ),
            )
        )
    db.add(
        AuthAttempt(
            id=uuid4(),
            identity_hash=identity_hash,
            ip_hash=ip_hash,
            accepted=accepted,
            created_at=now,
        )
    )
    db.execute(
        delete(AuthAttempt).where(AuthAttempt.created_at < now - timedelta(days=1))
    )
