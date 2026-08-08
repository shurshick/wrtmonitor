import asyncio
import base64
import json
from urllib.parse import urlparse
from uuid import UUID

from fastapi import (
    APIRouter,
    Cookie,
    Depends,
    Header,
    HTTPException,
    Request,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from ..config import Settings, load_settings
from ..db import get_db
from ..models import TerminalSession
from ..services.auth import device_from_token, web_user_from_session
from ..services.devices import get_user_device_or_404
from ..services.terminal_broker import (
    FINAL_STATUSES,
    MAX_FRAME_BYTES,
    append_terminal_frame,
    broker_session,
    close_terminal_session,
    create_terminal_session,
    get_terminal_session,
    normalize_terminal_size,
    set_terminal_status,
    terminal_frames_after,
    trim_terminal_frames,
)

router = APIRouter(prefix="/api/v1", tags=["terminal"])


def _websocket_is_same_origin(websocket: WebSocket) -> bool:
    origin = websocket.headers.get("origin")
    host = websocket.headers.get("host")
    if not origin or not host:
        return False
    parsed = urlparse(origin)
    return parsed.scheme in {"http", "https"} and parsed.netloc.lower() == host.lower()


def _load_browser_batch(
    session_id: UUID, after_id: int
) -> tuple[TerminalSession | None, list]:
    with broker_session() as db:
        terminal = get_terminal_session(db, session_id)
        if terminal is None:
            return None, []
        frames = terminal_frames_after(
            db,
            session_id=session_id,
            direction="up",
            after_id=after_id,
        )
        db.expunge(terminal)
        for frame in frames:
            db.expunge(frame)
        return terminal, frames


def _store_browser_frame(
    session_id: UUID,
    *,
    frame_type: str,
    payload: bytes | None = None,
    frame_data: dict | None = None,
) -> int:
    with broker_session() as db:
        frame = append_terminal_frame(
            db,
            session_id=session_id,
            direction="down",
            frame_type=frame_type,
            payload=payload,
            frame_data=frame_data,
        )
        db.commit()
        return frame.id


def _close_browser_session(session_id: UUID, reason: str) -> None:
    with broker_session() as db:
        close_terminal_session(db, session_id=session_id, reason=reason)
        db.commit()


async def _browser_terminal_output(websocket: WebSocket, session_id: UUID) -> None:
    after_id = 0
    last_status = ""
    while True:
        terminal, frames = await asyncio.to_thread(
            _load_browser_batch, session_id, after_id
        )
        if terminal is None:
            await websocket.send_json(
                {"type": "status", "status": "failed", "reason": "session missing"}
            )
            return
        if terminal.status != last_status:
            await websocket.send_json(
                {
                    "type": "status",
                    "session_id": str(session_id),
                    "status": terminal.status,
                    "reason": terminal.close_reason,
                }
            )
            last_status = terminal.status
        for frame in frames:
            after_id = frame.id
            if frame.frame_type == "data" and frame.payload:
                await websocket.send_json(
                    {
                        "type": "output",
                        "id": frame.id,
                        "data": base64.b64encode(frame.payload).decode("ascii"),
                    }
                )
        if terminal.status in FINAL_STATUSES and not frames:
            return
        await asyncio.sleep(0.12)


@router.websocket("/devices/{device_id}/terminal/ws")
async def browser_terminal_ws(
    websocket: WebSocket,
    device_id: UUID,
    columns: int = 80,
    rows: int = 24,
    wrtmonitor_session: str | None = Cookie(default=None),
    config: Settings = Depends(load_settings),
    db: Session = Depends(get_db),
):
    if not _websocket_is_same_origin(websocket):
        await websocket.close(code=1008, reason="same-origin connection required")
        return
    user = web_user_from_session(wrtmonitor_session, config, db)
    if not user:
        await websocket.close(code=1008, reason="authentication required")
        return
    try:
        get_user_device_or_404(db, user, device_id)
    except HTTPException:
        await websocket.close(code=1008, reason="device access denied")
        return

    columns, rows = normalize_terminal_size(columns, rows)
    terminal = create_terminal_session(
        db,
        device_id=device_id,
        user_id=user.id,
        columns=columns,
        rows=rows,
    )
    await websocket.accept()
    await websocket.send_json(
        {
            "type": "session",
            "session_id": str(terminal.id),
            "status": terminal.status,
            "columns": terminal.columns,
            "rows": terminal.rows,
        }
    )
    output_task = asyncio.create_task(_browser_terminal_output(websocket, terminal.id))
    close_reason = "browser disconnected"
    try:
        while True:
            message = await websocket.receive_json()
            frame_type = str(message.get("type") or "")
            if frame_type == "input":
                data = str(message.get("data") or "").encode("utf-8")
                if not data:
                    continue
                if len(data) > MAX_FRAME_BYTES:
                    await websocket.send_json(
                        {"type": "error", "message": "input frame is too large"}
                    )
                    continue
                await asyncio.to_thread(
                    _store_browser_frame,
                    terminal.id,
                    frame_type="data",
                    payload=data,
                )
            elif frame_type == "resize":
                try:
                    new_columns, new_rows = normalize_terminal_size(
                        int(message.get("columns") or columns),
                        int(message.get("rows") or rows),
                    )
                except (TypeError, ValueError):
                    await websocket.send_json(
                        {"type": "error", "message": "invalid terminal size"}
                    )
                    continue
                await asyncio.to_thread(
                    _store_browser_frame,
                    terminal.id,
                    frame_type="resize",
                    frame_data={"columns": new_columns, "rows": new_rows},
                )
            elif frame_type == "close":
                close_reason = "closed by user"
                break
            else:
                await websocket.send_json(
                    {"type": "error", "message": "unknown terminal frame"}
                )
    except WebSocketDisconnect:
        pass
    finally:
        await asyncio.to_thread(_close_browser_session, terminal.id, close_reason)
        output_task.cancel()
        await asyncio.gather(output_task, return_exceptions=True)


def _require_agent_terminal(
    db: Session,
    *,
    session_id: UUID,
    device_id: UUID,
) -> TerminalSession:
    terminal = get_terminal_session(db, session_id)
    if terminal is None:
        raise HTTPException(status_code=404, detail="Terminal session not found")
    if terminal.device_id != device_id:
        raise HTTPException(
            status_code=403, detail="Device token does not match terminal session"
        )
    return terminal


@router.get("/agent/terminal/sessions/{session_id}/down")
async def agent_terminal_down(
    session_id: UUID,
    after: int = 0,
    wait_seconds: int = 15,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    device = device_from_token(authorization, db)
    _require_agent_terminal(db, session_id=session_id, device_id=device.id)
    wait_seconds = max(0, min(wait_seconds, 25))

    async def event_generator():
        deadline = asyncio.get_running_loop().time() + wait_seconds
        while True:
            with broker_session() as broker_db:
                terminal = _require_agent_terminal(
                    broker_db, session_id=session_id, device_id=device.id
                )
                frames = terminal_frames_after(
                    broker_db,
                    session_id=session_id,
                    direction="down",
                    after_id=after,
                )
                terminal_status = terminal.status
            if frames:
                for frame in frames:
                    item = {
                        "id": frame.id,
                        "type": frame.frame_type,
                        **(frame.frame_data or {}),
                    }
                    if frame.payload is not None:
                        item["data"] = base64.b64encode(frame.payload).decode("ascii")
                    yield json.dumps(item, separators=(",", ":")) + "\n"
                return
            if terminal_status in FINAL_STATUSES:
                yield (
                    json.dumps(
                        {"id": after, "type": "close", "reason": terminal_status},
                        separators=(",", ":"),
                    )
                    + "\n"
                )
                return
            if asyncio.get_running_loop().time() >= deadline:
                yield json.dumps({"id": after, "type": "ping"}) + "\n"
                return
            await asyncio.sleep(0.15)

    return StreamingResponse(event_generator(), media_type="application/x-ndjson")


@router.put("/agent/terminal/sessions/{session_id}/up")
async def agent_terminal_up(
    session_id: UUID,
    request: Request,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    device = device_from_token(authorization, db)
    _require_agent_terminal(db, session_id=session_id, device_id=device.id)
    with broker_session() as broker_db:
        try:
            set_terminal_status(broker_db, session_id=session_id, status="connected")
        except RuntimeError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        broker_db.commit()
    stored = 0
    async for chunk in request.stream():
        for offset in range(0, len(chunk), MAX_FRAME_BYTES):
            part = chunk[offset : offset + MAX_FRAME_BYTES]
            if not part:
                continue
            with broker_session() as broker_db:
                append_terminal_frame(
                    broker_db,
                    session_id=session_id,
                    direction="up",
                    frame_type="data",
                    payload=part,
                )
                stored += len(part)
                trim_terminal_frames(broker_db, session_id)
                broker_db.commit()
    return {"status": "ok", "bytes": stored}


@router.post("/agent/terminal/sessions/{session_id}/status")
async def agent_terminal_status(
    session_id: UUID,
    request: Request,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    device = device_from_token(authorization, db)
    _require_agent_terminal(db, session_id=session_id, device_id=device.id)
    body = await request.json()
    status = str(body.get("status") or "")
    reason = str(body.get("reason") or "")[:500] or None
    if status not in {"connecting", "connected", "closed", "failed"}:
        raise HTTPException(status_code=422, detail="Invalid terminal status")
    with broker_session() as broker_db:
        try:
            set_terminal_status(
                broker_db, session_id=session_id, status=status, reason=reason
            )
        except RuntimeError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        broker_db.commit()
    return {"status": "ok"}
