from __future__ import annotations

import asyncio
import json
import logging
from collections import defaultdict
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any, AsyncIterator
from uuid import UUID

from sqlalchemy.orm import Session


logger = logging.getLogger(__name__)


class RealtimeBroker:
    """Process-local wake-up and broadcast layer; PostgreSQL remains authoritative."""

    def __init__(self) -> None:
        self._loop: asyncio.AbstractEventLoop | None = None
        self._sequence = 0
        self._generation: dict[UUID, int] = defaultdict(int)
        self._conditions: dict[UUID, asyncio.Condition] = {}
        self._subscribers: dict[UUID, set[asyncio.Queue[dict[str, Any]]]] = defaultdict(
            set
        )
        self.long_poll_active = 0
        self.long_poll_wakeups = 0
        self.long_poll_timeouts = 0
        self.events_published = 0
        self.events_dropped = 0

    def bind(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    def publish_local(
        self, device_id: UUID, event_type: str, data: dict[str, Any] | None = None
    ) -> None:
        loop = self._loop
        if loop is None or loop.is_closed():
            return
        loop.call_soon_threadsafe(
            lambda: asyncio.create_task(
                self._publish(device_id, event_type, data or {})
            )
        )

    async def _publish(
        self, device_id: UUID, event_type: str, data: dict[str, Any]
    ) -> None:
        self._sequence += 1
        self._generation[device_id] += 1
        payload = {
            "id": self._sequence,
            "type": event_type,
            "device_id": str(device_id),
            "emitted_at": datetime.now(UTC).isoformat(),
            "data": data,
        }
        self.events_published += 1
        for queue in tuple(self._subscribers.get(device_id, ())):
            if queue.full():
                self.events_dropped += 1
                while not queue.empty():
                    queue.get_nowait()
                queue.put_nowait({**payload, "type": "resync_required", "data": {}})
            else:
                queue.put_nowait(payload)
        condition = self._conditions.setdefault(device_id, asyncio.Condition())
        async with condition:
            condition.notify_all()

    def generation(self, device_id: UUID) -> int:
        return self._generation[device_id]

    async def wait_for_change(
        self, device_id: UUID, generation: int, timeout: float
    ) -> bool:
        if self._generation[device_id] != generation:
            return True
        condition = self._conditions.setdefault(device_id, asyncio.Condition())
        self.long_poll_active += 1
        try:
            async with condition:
                try:
                    await asyncio.wait_for(
                        condition.wait_for(
                            lambda: self._generation[device_id] != generation
                        ),
                        timeout=timeout,
                    )
                    self.long_poll_wakeups += 1
                    return True
                except TimeoutError:
                    self.long_poll_timeouts += 1
                    return False
        finally:
            self.long_poll_active -= 1

    @asynccontextmanager
    async def subscribe(
        self, device_id: UUID
    ) -> AsyncIterator[asyncio.Queue[dict[str, Any]]]:
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=64)
        self._subscribers[device_id].add(queue)
        try:
            yield queue
        finally:
            self._subscribers[device_id].discard(queue)

    def metrics(self) -> dict[str, int]:
        return {
            "long_poll_active": self.long_poll_active,
            "long_poll_wakeups": self.long_poll_wakeups,
            "long_poll_timeouts": self.long_poll_timeouts,
            "events_published": self.events_published,
            "events_dropped": self.events_dropped,
            "sse_subscribers": sum(len(value) for value in self._subscribers.values()),
        }


broker = RealtimeBroker()


def queue_realtime_event(
    db: Session,
    device_id: UUID,
    event_type: str,
    data: dict[str, Any] | None = None,
) -> None:
    from sqlalchemy import text

    payload = json.dumps(
        {"device_id": str(device_id), "type": event_type, "data": data or {}}
    )
    if hasattr(db, "execute"):
        db.execute(
            text("SELECT pg_notify('wrtmonitor_events', :payload)"),
            {"payload": payload},
        )
    else:
        # Mock mode for unit tests
        broker.publish_local(device_id, event_type, data)


def psycopg_connection_url(database_url: str) -> str:
    """Return a libpq-compatible DSN from the SQLAlchemy application URL."""
    for prefix in ("postgresql+psycopg://", "postgresql+psycopg2://"):
        if database_url.startswith(prefix):
            return "postgresql://" + database_url.removeprefix(prefix)
    if database_url.startswith("postgres://"):
        return "postgresql://" + database_url.removeprefix("postgres://")
    return database_url


async def listen_to_postgres(
    database_url: str, ready_event: asyncio.Event | None = None
) -> None:
    from psycopg import AsyncConnection

    url = psycopg_connection_url(database_url)

    while True:
        try:
            async with await AsyncConnection.connect(url, autocommit=True) as aconn:
                await aconn.execute("LISTEN wrtmonitor_events")
                if ready_event is not None:
                    ready_event.set()
                while True:
                    async for notify in aconn.notifies(timeout=1.0):
                        try:
                            payload = json.loads(notify.payload)
                            device_id = UUID(payload["device_id"])
                            event_type = payload["type"]
                            data = payload.get("data", {})
                            broker.publish_local(device_id, event_type, data)
                        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
                            logger.warning(
                                "Discarding malformed PostgreSQL realtime notification",
                                exc_info=True,
                            )
                    await asyncio.sleep(0)
        except asyncio.CancelledError:
            raise
        except Exception:
            if ready_event is not None:
                ready_event.clear()
            logger.exception("PostgreSQL realtime listener disconnected")
            await asyncio.sleep(5)


def sse_message(event: dict[str, Any]) -> str:
    data = json.dumps(event, ensure_ascii=False, separators=(",", ":"))
    return f"id: {event['id']}\nevent: {event['type']}\ndata: {data}\n\n"
