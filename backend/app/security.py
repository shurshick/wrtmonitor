from datetime import UTC, datetime, timedelta
from hashlib import sha256
from typing import Any
from uuid import UUID, uuid4

import jwt
from argon2 import PasswordHasher

from .config import Settings


_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except Exception:
        return False


def hash_token(token: str) -> str:
    return sha256(token.encode("utf-8")).hexdigest()


def _create_user_token(
    user_id: UUID, role: str, token_type: str, lifetime: timedelta, config: Settings
) -> str:
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "role": role,
        "type": token_type,
        "iat": int(now.timestamp()),
        "exp": int((now + lifetime).timestamp()),
    }
    return jwt.encode(payload, config.jwt_secret, algorithm="HS256")


def create_access_token(user_id: UUID, role: str, config: Settings) -> str:
    return _create_user_token(user_id, role, "access", timedelta(minutes=15), config)


def create_web_session_token(user_id: UUID, role: str, config: Settings) -> str:
    return _create_user_token(user_id, role, "access", timedelta(hours=8), config)


def create_refresh_token(
    user_id: UUID, role: str, session_id: UUID, config: Settings
) -> str:
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "role": role,
        "type": "refresh",
        "jti": str(session_id),
        "nonce": str(uuid4()),
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(days=30)).timestamp()),
    }
    return jwt.encode(payload, config.jwt_secret, algorithm="HS256")


def decode_access_token(token: str, config: Settings) -> dict[str, Any]:
    payload = jwt.decode(token, config.jwt_secret, algorithms=["HS256"])
    if payload.get("type") != "access":
        raise jwt.InvalidTokenError("unexpected token type")
    return payload


def decode_refresh_token(token: str, config: Settings) -> dict[str, Any]:
    payload = jwt.decode(token, config.jwt_secret, algorithms=["HS256"])
    if payload.get("type") != "refresh":
        raise jwt.InvalidTokenError("unexpected token type")
    return payload
