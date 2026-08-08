import base64
import json
import time

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.db import get_engine
from backend.app.main import app
from backend.app.models import TerminalFrame, TerminalSession
from backend.tests.test_api import clear_database, postgres_e2e_enabled


def test_browser_server_agent_terminal_roundtrip():
    if not postgres_e2e_enabled():
        pytest.skip("PostgreSQL E2E test requires WRTMONITOR_DATABASE_URL")

    clear_database()
    with TestClient(app) as client:
        setup = client.post(
            "/api/v1/setup/complete",
            json={
                "username": "terminal@example.com",
                "password": "terminal-test-password",
                "password_confirm": "terminal-test-password",
                "server_url": "http://127.0.0.1:8080",
            },
        )
        assert setup.status_code == 200
        api_login = client.post(
            "/api/v1/auth/login",
            json={
                "username": "terminal@example.com",
                "password": "terminal-test-password",
            },
        )
        owner_headers = {"Authorization": f"Bearer {api_login.json()['access_token']}"}
        provision = client.post(
            "/api/v1/devices/provision",
            headers=owner_headers,
            json={
                "name": "Terminal Router",
                "hostname": "terminal-openwrt",
                "model": "CI",
                "firmware": "OpenWrt",
            },
        ).json()
        device_id = provision["device_id"]
        agent_headers = {"Authorization": f"Bearer {provision['device_token']}"}
        web_login = client.post(
            "/login",
            data={
                "username": "terminal@example.com",
                "password": "terminal-test-password",
            },
            follow_redirects=False,
        )
        assert web_login.status_code == 303
        assert client.cookies.get("wrtmonitor_session")

        with client.websocket_connect(
            f"/api/v1/devices/{device_id}/terminal/ws?columns=132&rows=36",
            headers={"Origin": "http://testserver"},
        ) as websocket:
            session_message = websocket.receive_json()
            assert session_message["type"] == "session"
            assert session_message["columns"] == 132
            assert session_message["rows"] == 36
            session_id = session_message["session_id"]

            commands = client.get(
                "/api/v1/agent/commands", headers=agent_headers
            ).json()
            command = next(
                item for item in commands if item["type"] == "agent.ssh_session"
            )
            assert command["payload"]["session_id"] == session_id
            client.post(
                f"/api/v1/agent/commands/{command['id']}/result",
                headers=agent_headers,
                json={"status": "running", "result": {}},
            ).raise_for_status()
            client.post(
                f"/api/v1/agent/terminal/sessions/{session_id}/status",
                headers=agent_headers,
                json={"status": "connected"},
            ).raise_for_status()

            websocket.send_json({"type": "resize", "columns": "invalid", "rows": 36})
            resize_error = None
            for _ in range(8):
                message = websocket.receive_json()
                if message.get("type") == "error":
                    resize_error = message
                    break
            assert resize_error == {
                "type": "error",
                "message": "invalid terminal size",
            }
            websocket.send_json({"type": "resize", "columns": 120, "rows": 32})
            marker = "wrtmonitor-terminal-roundtrip"
            websocket.send_json({"type": "input", "data": marker + "\n"})
            down = client.get(
                f"/api/v1/agent/terminal/sessions/{session_id}/down",
                params={"after": 0, "wait_seconds": 1},
                headers=agent_headers,
            )
            frames = [json.loads(line) for line in down.text.splitlines()]
            resize_frame = next(item for item in frames if item["type"] == "resize")
            assert resize_frame["columns"] == 120
            assert resize_frame["rows"] == 32
            after_id = max(item["id"] for item in frames)
            down = client.get(
                f"/api/v1/agent/terminal/sessions/{session_id}/down",
                params={"after": after_id, "wait_seconds": 1},
                headers=agent_headers,
            )
            frames = [json.loads(line) for line in down.text.splitlines()]
            data_frame = next(item for item in frames if item["type"] == "data")
            assert base64.b64decode(data_frame["data"]) == (marker + "\n").encode()

            output = b"OpenWrt PTY: " + marker.encode() + b"\r\n"
            upload = client.put(
                f"/api/v1/agent/terminal/sessions/{session_id}/up",
                headers=agent_headers,
                content=output,
            )
            assert upload.json() == {"status": "ok", "bytes": len(output)}

            messages = []
            for _ in range(8):
                message = websocket.receive_json()
                messages.append(message)
                if message.get("type") == "output":
                    break
            output_message = next(
                item for item in messages if item.get("type") == "output"
            )
            assert base64.b64decode(output_message["data"]) == output
            websocket.send_json({"type": "close"})

        deadline = time.monotonic() + 2
        terminal_status = None
        while time.monotonic() < deadline:
            with Session(get_engine()) as db:
                terminal_status = db.scalar(select(TerminalSession.status))
            if terminal_status == "closed":
                break
            time.sleep(0.05)
        assert terminal_status == "closed"
        late_upload = client.put(
            f"/api/v1/agent/terminal/sessions/{session_id}/up",
            headers=agent_headers,
            content=b"late output",
        )
        assert late_upload.status_code == 409
        with Session(get_engine()) as db:
            directions = set(db.scalars(select(TerminalFrame.direction)).all())
        assert directions == {"down", "up"}
