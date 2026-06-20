from fastapi import Cookie, Depends, HTTPException
from sqlalchemy.orm import Session

from ..config import Settings
from ..db import get_db
from ..models import User
from ..services.auth import settings, web_user_from_session
from ..services.setup import is_setup_required


def require_web_user(
    wrtmonitor_session: str | None = Cookie(default=None),
    config: Settings = Depends(settings),
    db: Session = Depends(get_db),
) -> User:
    user = web_user_from_session(wrtmonitor_session, config, db)
    if not user:
        raise HTTPException(status_code=401, detail="Web session required")
    return user


def setup_required(
    config: Settings = Depends(settings), db: Session = Depends(get_db)
) -> bool:
    return is_setup_required(db, config)
