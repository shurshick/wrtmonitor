import hashlib
import hmac

from fastapi import HTTPException

from ..config import Settings


def generate_csrf_token(session_token: str, secret: str) -> str:
    if not session_token or not secret:
        raise ValueError("session token and secret are required")
    return hmac.new(secret.encode(), session_token.encode(), hashlib.sha256).hexdigest()


def verify_csrf_token(session_token: str, csrf_token: str, secret: str) -> bool:
    if not session_token or not csrf_token or not secret:
        return False
    expected = generate_csrf_token(session_token, secret)
    return hmac.compare_digest(expected, csrf_token)


def require_web_csrf(
    session_token: str | None, csrf_token: str, config: Settings
) -> None:
    if not session_token or not verify_csrf_token(
        session_token, csrf_token, config.jwt_secret
    ):
        raise HTTPException(status_code=403, detail="Invalid CSRF token")
