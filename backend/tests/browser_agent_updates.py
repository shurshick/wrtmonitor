from pathlib import Path

import httpx
from playwright.sync_api import expect


def check_agent_updates(
    page, base_url, device_id, device_token, artifacts: Path, username, password
):
    artifacts.mkdir(parents=True, exist_ok=True)
    cases = [
        (
            "older",
            "1.0.0",
            "0.55.5",
            "skipped",
            "downgrade blocked",
            "source_older",
            "Источник старее агента",
            None,
        ),
        ("current", "1.0.1", "1.0.1", "skipped", "", "current", "Агент актуален", None),
        (
            "available",
            "1.0.0",
            "1.0.1",
            "skipped",
            "",
            "available",
            "Есть обновление",
            "1.0.1",
        ),
        (
            "failed",
            "1.0.1",
            "1.0.1",
            "failed",
            "checksum verification failed",
            "error",
            "Проверка не удалась",
            None,
        ),
        (
            "newer-agent",
            "1.1.0",
            "1.0.1",
            "skipped",
            "downgrade blocked",
            "source_older",
            "Источник старее агента",
            None,
        ),
    ]
    with httpx.Client(base_url=base_url, timeout=15) as client:
        login = client.post(
            "/api/v1/auth/login", json={"username": username, "password": password}
        )
        login.raise_for_status()
        owner_headers = {"Authorization": "Bearer " + login.json()["access_token"]}
        for name, installed, source, status, error, state, label, candidate in cases:
            response = client.post(
                "/api/v1/agent/telemetry",
                headers={"Authorization": f"Bearer {device_token}"},
                json={
                    "device_id": device_id,
                    "telemetry": {
                        "schema_version": 2,
                        "agent": {
                            "version": installed,
                            "status": "running",
                            "available_version": source,
                            "last_update_status": status,
                            "last_update_error": error,
                            "last_update_check": "2026-10-05T11:56:57Z",
                            "capabilities": {
                                "agent.update": True,
                                "agent.set_interval": True,
                            },
                        },
                    },
                },
            )
            response.raise_for_status()
            page.goto(
                f"{base_url}/devices/{device_id}?section=management",
                wait_until="domcontentloaded",
            )
            card = page.locator(".maintenance-card").filter(
                has=page.get_by_role("heading", name="Обновление агента", exact=True)
            )
            expect(card).to_contain_text(label)
            available = (
                card.locator("dt")
                .filter(has_text="Доступное обновление")
                .locator("+ dd")
            )
            expect(available).to_have_text(
                candidate or ("Не проверено" if state == "error" else "Нет")
            )
            if state == "error":
                expect(card.locator(".error")).to_have_text(error)
            else:
                assert card.locator(".error").count() == 0
                assert "downgrade blocked" not in card.inner_text()
            if name == "newer-agent":
                expect(
                    page.get_by_text("Сервер старее агента", exact=True)
                ).to_be_visible()
                assert (
                    page.get_by_text("Агент требует обновления", exact=True).count()
                    == 0
                )
            api = client.get(
                f"/api/v1/devices/{device_id}/agent", headers=owner_headers
            )
            api.raise_for_status()
            observed = api.json()
            assert observed["available_version"] == source
            assert observed["last_update_error"] == error
            assert observed["update_view"]["state"] == state
            assert observed["update_view"]["available_version"] == candidate
            if name == "older":
                page.screenshot(
                    path=str(artifacts / "agent-update-old-source.png"), full_page=True
                )
