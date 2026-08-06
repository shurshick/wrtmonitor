import asyncio
from uuid import UUID
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from sqlalchemy.orm import Session
from .auth import current_user

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
    # Authentication usually requires a token in query param for WebSockets since browsers don't send auth headers easily
):
    await websocket.accept()

    # Simple check for now (in production we'd parse token from query param)
    browser_connections[device_id] = websocket

    try:
        # Request the agent to start an SSH session if it's not already connected
        # In a real implementation, we'd trigger a device command 'agent.ssh_session'

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
    # Authentication usually requires token header, which curl/websocat can provide
):
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
