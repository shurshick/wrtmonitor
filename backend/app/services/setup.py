from datetime import UTC, datetime
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import Settings, validate_server_url
from ..models import AppSetting, User
from ..schemas import SetupRequest
from ..security import hash_password
from .audit import audit


def get_public_server_url(db: Session, config: Settings) -> str | None:
    if config.public_server_url:
        return config.public_server_url
    setting = db.get(AppSetting, "public_server_url")
    return setting.value if setting else None


def has_admin(db: Session) -> bool:
    return db.scalar(select(User.id).limit(1)) is not None


def is_setup_required(db: Session, config: Settings) -> bool:
    return not has_admin(db) or not get_public_server_url(db, config)


def complete_setup(
    payload: SetupRequest, config: Settings, db: Session
) -> dict[str, str]:
    if has_admin(db):
        raise HTTPException(status_code=409, detail="Administrator already exists")
    if payload.password != payload.password_confirm:
        raise HTTPException(status_code=400, detail="Passwords do not match")
    server_url = validate_server_url(payload.server_url, config.allow_insecure_local)
    now = datetime.now(UTC)
    user = User(
        id=uuid4(),
        username=payload.username.strip(),
        password_hash=hash_password(payload.password),
        role="owner",
        disabled=False,
        created_at=now,
        updated_at=now,
    )
    db.add(user)
    db.flush()
    db.add(AppSetting(key="public_server_url", value=server_url, updated_at=now))
    audit(db, user.id, "setup.complete", "server", None, {"server_url": server_url})
    db.commit()
    return {"server_url": server_url}
