from __future__ import annotations

from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from typing import Iterator
from uuid import UUID, uuid4

from sqlalchemy import delete, select
from sqlalchemy.orm import Session, sessionmaker

from ..db import get_engine
from ..models import TerminalFrame, TerminalSession
from .commands import create_device_command


ACTIVE_STATUSES = {"queued", "connecting", "connected"}
FINAL_STATUSES = {"closed", "failed", "expired"}
SESSION_TTL = timedelta(minutes=30)
SESSION_RETENTION = timedelta(days=1)
MAX_FRAME_BYTES = 64 * 1024
MAX_SESSION_FRAMES = 20_000


def now_utc() -> datetime:
    return datetime.now(UTC)


def normalize_terminal_size(columns: int, rows: int) -> tuple[int, int]:
    return max(20, min(int(columns), 400)), max(5, min(int(rows), 120))


@contextmanager
def broker_session() -> Iterator[Session]:
    factory = sessionmaker(bind=get_engine(), autoflush=False, expire_on_commit=False)
    with factory() as db:
        yield db


def create_terminal_session(
    db: Session,
    *,
    device_id: UUID,
    user_id: UUID,
    columns: int = 80,
    rows: int = 24,
) -> TerminalSession:
    columns, rows = normalize_terminal_size(columns, rows)
    now = now_utc()
    terminal = TerminalSession(
        id=uuid4(),
        device_id=device_id,
        user_id=user_id,
        command_id=None,
        status="queued",
        columns=columns,
        rows=rows,
        created_at=now,
        updated_at=now,
        last_activity_at=now,
        expires_at=now + SESSION_TTL,
    )
    db.add(terminal)
    db.flush()
    command = create_device_command(
        db=db,
        device_id=device_id,
        command_type="agent.ssh_session",
        payload={
            "session_id": str(terminal.id),
            "columns": columns,
            "rows": rows,
        },
        created_by=user_id,
        source="web",
        idempotency_key=f"terminal:{terminal.id}",
    )
    terminal.command_id = command.id
    db.commit()
    return terminal


def get_terminal_session(db: Session, session_id: UUID) -> TerminalSession | None:
    return db.get(TerminalSession, session_id)


def append_terminal_frame(
    db: Session,
    *,
    session_id: UUID,
    direction: str,
    frame_type: str,
    payload: bytes | None = None,
    frame_data: dict | None = None,
) -> TerminalFrame:
    if direction not in {"down", "up"}:
        raise ValueError("invalid terminal frame direction")
    if frame_type not in {"data", "resize", "close"}:
        raise ValueError("invalid terminal frame type")
    if payload is not None and len(payload) > MAX_FRAME_BYTES:
        raise ValueError("terminal frame is too large")
    terminal = db.get(TerminalSession, session_id)
    if terminal is None:
        raise LookupError("terminal session not found")
    if terminal.status in FINAL_STATUSES:
        raise RuntimeError("terminal session is closed")
    now = now_utc()
    frame = TerminalFrame(
        session_id=session_id,
        direction=direction,
        frame_type=frame_type,
        payload=payload,
        frame_data=frame_data or {},
        created_at=now,
    )
    terminal.last_activity_at = now
    terminal.updated_at = now
    terminal.expires_at = now + SESSION_TTL
    db.add(frame)
    db.flush()
    return frame


def terminal_frames_after(
    db: Session,
    *,
    session_id: UUID,
    direction: str,
    after_id: int,
    limit: int = 128,
) -> list[TerminalFrame]:
    return list(
        db.scalars(
            select(TerminalFrame)
            .where(
                TerminalFrame.session_id == session_id,
                TerminalFrame.direction == direction,
                TerminalFrame.id > max(0, after_id),
            )
            .order_by(TerminalFrame.id)
            .limit(max(1, min(limit, 512)))
        )
    )


def set_terminal_status(
    db: Session,
    *,
    session_id: UUID,
    status: str,
    reason: str | None = None,
) -> TerminalSession:
    if status not in ACTIVE_STATUSES | FINAL_STATUSES:
        raise ValueError("invalid terminal session status")
    terminal = db.get(TerminalSession, session_id)
    if terminal is None:
        raise LookupError("terminal session not found")
    if terminal.status in FINAL_STATUSES:
        if status in FINAL_STATUSES:
            return terminal
        raise RuntimeError("terminal session is already closed")
    now = now_utc()
    terminal.status = status
    terminal.updated_at = now
    terminal.last_activity_at = now
    if status == "connected" and terminal.connected_at is None:
        terminal.connected_at = now
    if status in FINAL_STATUSES:
        terminal.closed_at = now
        terminal.close_reason = (reason or status)[:500]
    db.flush()
    return terminal


def close_terminal_session(
    db: Session,
    *,
    session_id: UUID,
    reason: str,
) -> TerminalSession | None:
    terminal = db.get(TerminalSession, session_id)
    if terminal is None:
        return None
    if terminal.status not in FINAL_STATUSES:
        append_terminal_frame(
            db,
            session_id=session_id,
            direction="down",
            frame_type="close",
            frame_data={"reason": reason[:500]},
        )
        set_terminal_status(db, session_id=session_id, status="closed", reason=reason)
    return terminal


def trim_terminal_frames(db: Session, session_id: UUID) -> int:
    keep_from = db.scalar(
        select(TerminalFrame.id)
        .where(TerminalFrame.session_id == session_id)
        .order_by(TerminalFrame.id.desc())
        .offset(MAX_SESSION_FRAMES)
        .limit(1)
    )
    if keep_from is None:
        return 0
    result = db.execute(
        delete(TerminalFrame).where(
            TerminalFrame.session_id == session_id,
            TerminalFrame.id <= keep_from,
        )
    )
    return int(result.rowcount or 0)


def cleanup_terminal_sessions(
    db: Session, *, now: datetime | None = None
) -> dict[str, int]:
    current = now or now_utc()
    expired = 0
    active_sessions = db.scalars(
        select(TerminalSession).where(
            TerminalSession.status.in_(ACTIVE_STATUSES),
            TerminalSession.expires_at < current,
        )
    ).all()
    for terminal in active_sessions:
        set_terminal_status(
            db,
            session_id=terminal.id,
            status="expired",
            reason="terminal session timed out",
        )
        expired += 1

    result = db.execute(
        delete(TerminalSession).where(
            TerminalSession.status.in_(FINAL_STATUSES),
            TerminalSession.closed_at < current - SESSION_RETENTION,
        )
    )
    return {"expired": expired, "deleted": int(result.rowcount or 0)}
