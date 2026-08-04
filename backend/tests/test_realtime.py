import asyncio
from uuid import uuid4

from fastapi.testclient import TestClient

import backend.app.api.agent as agent_api
from backend.app.main import app
from backend.app.services.realtime import RealtimeBroker, sse_message


def test_realtime_broker_broadcasts_without_consuming_another_subscriber_event():
    async def scenario():
        broker = RealtimeBroker()
        broker.bind(asyncio.get_running_loop())
        device_id = uuid4()
        async with broker.subscribe(device_id) as first:
            async with broker.subscribe(device_id) as second:
                broker.publish_local(device_id, "telemetry.updated", {"status": "online"})
                left, right = await asyncio.gather(
                    asyncio.wait_for(first.get(), 1),
                    asyncio.wait_for(second.get(), 1),
                )
                assert left == right
                assert left["type"] == "telemetry.updated"
                assert left["data"]["status"] == "online"

    asyncio.run(scenario())


def test_long_poll_wakes_after_device_event():
    async def scenario():
        broker = RealtimeBroker()
        broker.bind(asyncio.get_running_loop())
        device_id = uuid4()
        generation = broker.generation(device_id)
        waiter = asyncio.create_task(broker.wait_for_change(device_id, generation, 1))
        await asyncio.sleep(0)
        broker.publish_local(device_id, "command.queued", {})
        assert await waiter is True
        assert broker.metrics()["long_poll_wakeups"] == 1

    asyncio.run(scenario())


def test_realtime_broker_wakes_one_hundred_waiting_agents():
    async def scenario():
        broker = RealtimeBroker()
        broker.bind(asyncio.get_running_loop())
        devices = [uuid4() for _ in range(100)]
        waiters = [
            asyncio.create_task(
                broker.wait_for_change(device_id, broker.generation(device_id), 1)
            )
            for device_id in devices
        ]
        await asyncio.sleep(0)
        for device_id in devices:
            broker.publish_local(device_id, "command.queued", {})
        assert all(await asyncio.gather(*waiters))
        assert broker.metrics()["long_poll_active"] == 0
        assert broker.metrics()["long_poll_wakeups"] == 100

    asyncio.run(scenario())


def test_sse_message_has_named_event_and_json_payload():
    message = sse_message(
        {
            "id": 7,
            "type": "command.status",
            "device_id": "router-1",
            "emitted_at": "2026-08-04T00:00:00+00:00",
            "data": {"status": "success"},
        }
    )
    assert "id: 7\n" in message
    assert "event: command.status\n" in message
    assert '"status":"success"' in message


def test_agent_long_poll_rechecks_queue_after_wakeup(monkeypatch):
    device_id = uuid4()
    command = {
        "id": str(uuid4()),
        "type": "diagnostics.run",
        "payload": {},
        "contract_version": 1,
    }
    claims = iter(([], [], [command]))

    class FakeBroker:
        def generation(self, requested_device_id):
            assert requested_device_id == device_id
            return 3

        async def wait_for_change(self, requested_device_id, generation, timeout):
            assert requested_device_id == device_id
            assert generation == 3
            assert timeout == 12
            return True

    monkeypatch.setattr(agent_api, "_authenticated_device_id", lambda _: device_id)
    monkeypatch.setattr(agent_api, "_claim_commands", lambda _: next(claims))
    monkeypatch.setattr(agent_api, "broker", FakeBroker())
    response = TestClient(app).get(
        "/api/v1/agent/commands?wait=12",
        headers={"Authorization": "Bearer device-token"},
    )
    assert response.status_code == 200
    assert response.json() == [command]


def test_legacy_agent_poll_does_not_wait(monkeypatch):
    device_id = uuid4()
    monkeypatch.setattr(agent_api, "_authenticated_device_id", lambda _: device_id)
    monkeypatch.setattr(agent_api, "_claim_commands", lambda _: [])
    response = TestClient(app).get(
        "/api/v1/agent/commands",
        headers={"Authorization": "Bearer device-token"},
    )
    assert response.status_code == 200
    assert response.json() == []
