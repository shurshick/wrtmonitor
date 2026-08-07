import asyncio
from uuid import UUID
from fastapi import (
    APIRouter,
    WebSocket,
    WebSocketDisconnect,
    Depends,
    Cookie,
    Header,
    Request,
    HTTPException,
)
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from ..config import Settings, load_settings
from ..db import get_db
from ..services.auth import web_user_from_session, device_from_token
from ..services.commands import create_device_command

router = APIRouter(prefix="/api/v1", tags=["ssh"])

# In-memory dictionary to hold browser WebSocket connections
browser_connections: dict[UUID, WebSocket] = {}

# In-memory dictionary to hold queues for sending data down to the agent
agent_down_queues: dict[UUID, asyncio.Queue] = {}


@router.websocket("/devices/{device_id}/ssh/ws")
async def browser_ssh_ws(
    websocket: WebSocket,
    device_id: UUID,
    wrtmonitor_session: str | None = Cookie(default=None),
    config: Settings = Depends(load_settings),
    db: Session = Depends(get_db),
):
    user = web_user_from_session(wrtmonitor_session, config, db)
    if not user:
        await websocket.close(code=1008)
        return

    await websocket.accept()
    browser_connections[device_id] = websocket

    if device_id not in agent_down_queues:
        agent_down_queues[device_id] = asyncio.Queue()

    try:
        # Wake up the agent
        create_device_command(
            db=db,
            device_id=device_id,
            command_type="agent.ssh_session",
            payload={},
            created_by=user.id,
            source="api",
        )
        try:
            db.commit()
        except Exception:
            db.rollback()

        while True:
            data = await websocket.receive_text()
            # Forward data to agent's down queue
            if device_id in agent_down_queues:
                await agent_down_queues[device_id].put(data.encode("utf-8"))

    except WebSocketDisconnect:
        if device_id in browser_connections:
            del browser_connections[device_id]
        if device_id in agent_down_queues:
            # send None to signal EOF to the agent
            await agent_down_queues[device_id].put(None)


@router.get("/agent/ssh/down/{device_id}")
async def agent_ssh_down(
    device_id: UUID,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    try:
        device_from_token(authorization, db)
    except Exception:
        raise HTTPException(status_code=401, detail="Unauthorized")

    if device_id not in agent_down_queues:
        agent_down_queues[device_id] = asyncio.Queue()

    queue = agent_down_queues[device_id]

    async def event_generator():
        try:
            while True:
                data = await queue.get()
                if data is None:
                    break
                yield data
        except asyncio.CancelledError:
            pass
        finally:
            # If the download connection drops, maybe we shouldn't kill the queue entirely,
            # but usually it means the agent disconnected.
            pass

    return StreamingResponse(event_generator(), media_type="application/octet-stream")


@router.put("/agent/ssh/up/{device_id}")
async def agent_ssh_up(
    device_id: UUID,
    request: Request,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    try:
        device_from_token(authorization, db)
    except Exception:
        raise HTTPException(status_code=401, detail="Unauthorized")

    browser_ws = browser_connections.get(device_id)
    if not browser_ws:
        return {"status": "ignored"}

    async for chunk in request.stream():
        # Using the current active browser WS
        current_ws = browser_connections.get(device_id)
        if current_ws:
            try:
                await current_ws.send_text(chunk.decode("utf-8", errors="replace"))
            except Exception:
                # Browser might have disconnected
                break
    return {"status": "ok"}
