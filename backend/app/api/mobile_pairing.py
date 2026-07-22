from datetime import UTC, datetime
from ipaddress import ip_address
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from ..config import Settings
from ..db import get_db
from ..models import User
from ..schemas import MobilePairingExchangeRequest
from ..security import create_access_token
from ..services.audit import audit
from ..services.auth import current_user, settings
from ..services.mobile_pairing import (
    create_pairing_token,
    enforce_pairing_rate_limit,
    get_user_pairing_token,
    locked_pairing_token,
    pairing_identity_hash,
    pairing_response,
    pairing_status,
    record_pairing_attempt,
)
from ..services.sessions import create_user_session
from ..services.setup import get_public_server_url


router = APIRouter(prefix="/api/v1/mobile-pairing", tags=["mobile-pairing"])


def pairing_error(status_code: int, code: str) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"code": code})


def require_owner(user: User) -> None:
    if user.disabled or user.role != "owner":
        raise pairing_error(403, "owner_required")


def request_ip(request: Request) -> str:
    transport_ip = request.client.host if request.client else "unknown"
    forwarded = request.headers.get("x-forwarded-for", "").split(",", 1)[0].strip()
    trusted_proxy = False
    try:
        transport_address = ip_address(transport_ip)
        trusted_proxy = transport_address.is_private or transport_address.is_loopback
    except ValueError:
        pass
    if forwarded and trusted_proxy:
        try:
            return str(ip_address(forwarded))
        except ValueError:
            pass
    return transport_ip[:64]


@router.post("/tokens")
def create_mobile_pairing_token(
    user: User = Depends(current_user),
    config: Settings = Depends(settings),
    db: Session = Depends(get_db),
) -> dict:
    require_owner(user)
    try:
        item, _, setup_payload = create_pairing_token(
            db, user, config, get_public_server_url(db, config)
        )
    except ValueError as exc:
        code = str(exc)
        if code == "pairing_rate_limited":
            raise pairing_error(429, code) from exc
        raise pairing_error(503, code) from exc
    audit(db, user.id, "mobile_pairing.token.created", "mobile_pairing", str(item.id))
    db.commit()
    return pairing_response(item) | {"setup_payload": setup_payload}


@router.get("/tokens/{pairing_id}")
def get_mobile_pairing_token(
    pairing_id: UUID,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict:
    require_owner(user)
    item = get_user_pairing_token(db, user.id, pairing_id)
    if not item:
        raise pairing_error(404, "pairing_not_found")
    return pairing_response(item)


@router.delete("/tokens/{pairing_id}")
def revoke_mobile_pairing_token(
    pairing_id: UUID,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict:
    require_owner(user)
    item = get_user_pairing_token(db, user.id, pairing_id)
    if not item:
        raise pairing_error(404, "pairing_not_found")
    if pairing_status(item) == "active":
        item.revoked_at = datetime.now(UTC)
        audit(
            db,
            user.id,
            "mobile_pairing.token.revoked",
            "mobile_pairing",
            str(item.id),
        )
        db.commit()
    return pairing_response(item)


@router.post("/exchange")
def exchange_mobile_pairing_token(
    request: Request,
    payload: MobilePairingExchangeRequest,
    config: Settings = Depends(settings),
    db: Session = Depends(get_db),
) -> dict:
    item, token_digest = locked_pairing_token(db, payload.pairing_token)
    identity_digest = pairing_identity_hash(request_ip(request), config)
    try:
        enforce_pairing_rate_limit(db, identity_digest, token_digest)
    except ValueError as exc:
        audit(db, item.user_id if item else None, "mobile_pairing.rate_limited")
        db.commit()
        raise pairing_error(429, "pairing_rate_limited") from exc

    if not item:
        record_pairing_attempt(db, identity_digest, token_digest, accepted=False)
        audit(db, None, "mobile_pairing.invalid_attempt")
        db.commit()
        raise pairing_error(401, "pairing_invalid")

    state = pairing_status(item)
    if state != "active":
        record_pairing_attempt(db, identity_digest, token_digest, accepted=False)
        audit(
            db,
            item.user_id,
            f"mobile_pairing.token.{state}_attempt",
            "mobile_pairing",
            str(item.id),
        )
        db.commit()
        raise pairing_error(410, f"pairing_{state}")

    public_server_url = get_public_server_url(db, config)
    if not public_server_url or item.server_url != public_server_url:
        record_pairing_attempt(db, identity_digest, token_digest, accepted=False)
        audit(
            db,
            item.user_id,
            "mobile_pairing.server_url_mismatch",
            "mobile_pairing",
            str(item.id),
        )
        db.commit()
        raise pairing_error(409, "pairing_server_changed")

    user = db.get(User, item.user_id)
    if not user or user.disabled or user.role != "owner":
        record_pairing_attempt(db, identity_digest, token_digest, accepted=False)
        db.commit()
        raise pairing_error(401, "pairing_invalid")

    session, refresh_token = create_user_session(
        db,
        user,
        config,
        client_name=payload.client_name,
        ip_address=request_ip(request),
        client_type="mobile_pairing",
    )
    now = datetime.now(UTC)
    item.used_at = now
    item.used_session_id = session.id
    record_pairing_attempt(db, identity_digest, token_digest, accepted=True)
    audit(
        db,
        user.id,
        "mobile_pairing.token.used",
        "mobile_pairing",
        str(item.id),
    )
    audit(
        db,
        user.id,
        "mobile_pairing.session.created",
        "session",
        str(session.id),
        {"client_type": "mobile_pairing"},
    )
    db.commit()
    return {
        "access_token": create_access_token(user.id, user.role, config),
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": 15 * 60,
        "server_url": item.server_url,
        "owner": {"username": user.username},
    }
