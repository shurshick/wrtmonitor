from uuid import UUID
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Cookie, Header
from sqlalchemy.orm import Session
from ..config import Settings, load_settings
from ..db import get_db
from ..services.auth import web_user_from_session, device_from_token
from ..services.commands import create_device_command

router = APIRouter(prefix="/api/v1", tags=["ssh"])

# In-memory dictionary to hold agent WebSocket connections
# Key: device_id (UUID), Value: WebSocket
agent_connections: dict[UUID, WebSocket] = {}

# In-memory dictionary to hold browser WebSocket connections
# Key: device_id (UUID), Value: WebSocket
browser_connections: dict[UUID, WebSocket] = {}


@router.websocket("/devices/{device_id}/ssh/ws")
async def browser_ssh_ws(
    websocket: WebSocket,
    device_id: UUID,
    wrtmonitor_session: str | None = Cookie(default=None),
    config: Settings = Depends(load_settings),
    db: Session = Depends(get_db),
):
    # Authenticate the user from the session cookie
    user = web_user_from_session(wrtmonitor_session, config, db)
    if not user:
        await websocket.close(code=1008)
        return

    await websocket.accept()
    browser_connections[device_id] = websocket

    try:
        # Request the agent to start an SSH session if it's not already connected
        if device_id not in agent_connections:
            # Wake up the agent
            create_device_command(
                db=db,
                device_id=device_id,
                command_type="agent.ssh_session",
                payload={},
                created_by=user.id,
                source="api"
            )
            try:
                db.commit()
            except Exception:
                db.rollback()

        while True:
            data = await websocket.receive_text()
            # Forward data to agent if connected
            agent_ws = agent_connections.get(device_id)
            if agent_ws:
                await agent_ws.send_text(data)
            else:
                # Agent not connected yet, queue or drop
                pass
    except WebSocketDisconnect:
        if device_id in browser_connections:
            del browser_connections[device_id]
        # Notify agent to close
        agent_ws = agent_connections.get(device_id)
        if agent_ws:
            try:
                await agent_ws.close()
            except Exception:
                pass


@router.websocket("/agent/ssh/ws/{device_id}")
async def agent_ssh_ws(
    websocket: WebSocket,
    device_id: UUID,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    try:
        # Authenticate the agent from the Authorization header
        device_from_token(authorization, db)
    except Exception:
        await websocket.close(code=1008)
        return

    await websocket.accept()
    agent_connections[device_id] = websocket

    try:
        while True:
            data = await websocket.receive_text()
            # Forward data to browser if connected
            browser_ws = browser_connections.get(device_id)
            if browser_ws:
                await browser_ws.send_text(data)
    except WebSocketDisconnect:
        if device_id in agent_connections:
            del agent_connections[device_id]
        # Notify browser to close
        browser_ws = browser_connections.get(device_id)
        if browser_ws:
            try:
                await browser_ws.close()
            except Exception:
                pass
