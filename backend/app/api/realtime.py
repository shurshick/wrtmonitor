from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Cookie, Header, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from ..config import load_settings
from ..db import get_engine
from ..services.auth import current_user, web_user_from_session
from ..services.devices import get_user_device_or_404
from ..services.realtime import broker, sse_message


router = APIRouter()


@router.get("/api/v1/devices/{device_id}/events")
def device_events(
    device_id: UUID,
    request: Request,
    authorization: str | None = Header(default=None),
    wrtmonitor_session: str | None = Cookie(default=None),
) -> StreamingResponse:
    with Session(get_engine()) as db:
        if authorization:
            user = current_user(authorization, load_settings(), db)
        else:
            user = web_user_from_session(wrtmonitor_session, load_settings(), db)
            if user is None:
                raise HTTPException(status_code=401, detail="Authentication required")
        get_user_device_or_404(db, user, device_id)

    async def stream():
        yield "retry: 3000\n\n"
        yield sse_message(
            {
                "id": 0,
                "type": "snapshot",
                "device_id": str(device_id),
                "emitted_at": datetime.now(UTC).isoformat(),
                "data": {},
            }
        )
        async with broker.subscribe(device_id) as queue:
            while not await request.is_disconnected():
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=15)
                    yield sse_message(event)
                except TimeoutError:
                    yield ": keepalive\n\n"

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
