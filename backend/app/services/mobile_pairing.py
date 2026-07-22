from __future__ import annotations

import hashlib
import hmac
import json
import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import delete, func, select, text
from sqlalchemy.orm import Session

from ..config import Settings, validate_server_url
from ..models import MobilePairingAttempt, MobilePairingToken, User
from ..security import hash_token


PAIRING_LIFETIME = timedelta(minutes=10)
PAIRING_TYPE = "wrtmonitor-mobile-setup"
PAIRING_VERSION = 1
IP_ATTEMPT_LIMIT = 10
TOKEN_ATTEMPT_LIMIT = 5
ATTEMPT_WINDOW = timedelta(minutes=1)


def pairing_status(item: MobilePairingToken, now: datetime | None = None) -> str:
    current = now or datetime.now(UTC)
    if item.revoked_at is not None:
        return "revoked"
    if item.used_at is not None:
        return "used"
    if item.expires_at <= current:
        return "expired"
    return "active"


def pairing_response(item: MobilePairingToken) -> dict[str, str | None]:
    return {
        "id": str(item.id),
        "status": pairing_status(item),
        "server_url": item.server_url,
        "created_at": item.created_at.isoformat(),
        "expires_at": item.expires_at.isoformat(),
        "used_at": item.used_at.isoformat() if item.used_at else None,
        "revoked_at": item.revoked_at.isoformat() if item.revoked_at else None,
        "session_id": str(item.used_session_id) if item.used_session_id else None,
    }


def create_pairing_token(
    db: Session, user: User, config: Settings, server_url: str | None
) -> tuple[MobilePairingToken, str, str]:
    if not server_url:
        raise ValueError("public_server_url_required")
    try:
        server_url = validate_server_url(server_url, config.allow_insecure_local)
    except ValueError as exc:
        raise ValueError("pairing_public_url_invalid") from exc
    now = datetime.now(UTC)
    db.execute(
        text("SELECT pg_advisory_xact_lock(hashtext(:identity))"),
        {"identity": f"mobile-pairing-user:{user.id}"},
    )
    recent_count = db.scalar(
        select(func.count())
        .select_from(MobilePairingToken)
        .where(
            MobilePairingToken.user_id == user.id,
            MobilePairingToken.created_at >= now - timedelta(minutes=1),
        )
    )
    if int(recent_count or 0) >= 5:
        raise ValueError("pairing_rate_limited")
    active_items = db.scalars(
        select(MobilePairingToken)
        .where(
            MobilePairingToken.user_id == user.id,
            MobilePairingToken.used_at.is_(None),
            MobilePairingToken.revoked_at.is_(None),
            MobilePairingToken.expires_at > now,
        )
        .with_for_update()
    ).all()
    for active_item in active_items:
        active_item.revoked_at = now
    raw_token = secrets.token_urlsafe(32)
    item = MobilePairingToken(
        id=uuid4(),
        user_id=user.id,
        token_hash=hash_token(raw_token),
        server_url=server_url,
        created_at=now,
        expires_at=now + PAIRING_LIFETIME,
        used_at=None,
        revoked_at=None,
        used_session_id=None,
    )
    db.add(item)
    payload = json.dumps(
        {
            "type": PAIRING_TYPE,
            "version": PAIRING_VERSION,
            "server_url": item.server_url,
            "pairing_token": raw_token,
        },
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    )
    return item, raw_token, payload


def pairing_identity_hash(ip_address: str, config: Settings) -> str:
    return hmac.new(
        config.jwt_secret.encode(),
        f"mobile-pairing-ip:{ip_address}".encode(),
        hashlib.sha256,
    ).hexdigest()


def enforce_pairing_rate_limit(
    db: Session, identity_hash: str, token_digest: str
) -> None:
    db.execute(
        text("SELECT pg_advisory_xact_lock(hashtext(:identity))"),
        {"identity": identity_hash},
    )
    db.execute(
        text("SELECT pg_advisory_xact_lock(hashtext(:token))"),
        {"token": token_digest},
    )
    cutoff = datetime.now(UTC) - ATTEMPT_WINDOW
    ip_count = db.scalar(
        select(func.count())
        .select_from(MobilePairingAttempt)
        .where(
            MobilePairingAttempt.identity_hash == identity_hash,
            MobilePairingAttempt.created_at >= cutoff,
        )
    )
    token_count = db.scalar(
        select(func.count())
        .select_from(MobilePairingAttempt)
        .where(
            MobilePairingAttempt.token_hash == token_digest,
            MobilePairingAttempt.created_at >= cutoff,
        )
    )
    if (
        int(ip_count or 0) >= IP_ATTEMPT_LIMIT
        or int(token_count or 0) >= TOKEN_ATTEMPT_LIMIT
    ):
        raise ValueError("pairing_rate_limited")


def record_pairing_attempt(
    db: Session, identity_hash: str, token_digest: str, *, accepted: bool
) -> None:
    now = datetime.now(UTC)
    db.add(
        MobilePairingAttempt(
            id=uuid4(),
            identity_hash=identity_hash,
            token_hash=token_digest,
            accepted=accepted,
            created_at=now,
        )
    )
    db.execute(
        delete(MobilePairingAttempt).where(
            MobilePairingAttempt.created_at < now - timedelta(days=1)
        )
    )


def locked_pairing_token(
    db: Session, raw_token: str
) -> tuple[MobilePairingToken | None, str]:
    digest = hash_token(raw_token)
    item = db.scalar(
        select(MobilePairingToken)
        .where(MobilePairingToken.token_hash == digest)
        .with_for_update()
    )
    return item, digest


def get_user_pairing_token(
    db: Session, user_id: UUID, pairing_id: UUID
) -> MobilePairingToken | None:
    return db.scalar(
        select(MobilePairingToken).where(
            MobilePairingToken.id == pairing_id,
            MobilePairingToken.user_id == user_id,
        )
    )
