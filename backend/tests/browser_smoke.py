from __future__ import annotations

import os
from pathlib import Path

import httpx
from playwright.sync_api import Page, sync_playwright


BASE_URL = os.getenv("WRTMONITOR_BROWSER_BASE_URL", "http://127.0.0.1:8090")
ARTIFACTS = Path(os.getenv("WRTMONITOR_BROWSER_ARTIFACTS", "artifacts/browser"))
USERNAME = "browser@example.com"
PASSWORD = "browser-test-password"


def prepare_router() -> str:
    with httpx.Client(base_url=BASE_URL, timeout=15) as client:
        setup = client.get("/api/v1/setup/status")
        setup.raise_for_status()
        if setup.json()["setup_required"]:
            response = client.post(
                "/api/v1/setup/complete",
                json={
                    "username": USERNAME,
                    "password": PASSWORD,
                    "password_confirm": PASSWORD,
                    "server_url": BASE_URL,
                },
            )
            response.raise_for_status()
        login = client.post(
            "/api/v1/auth/login",
            json={"username": USERNAME, "password": PASSWORD},
        )
        login.raise_for_status()
        owner_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
        provision = client.post(
            "/api/v1/devices/provision",
            headers=owner_headers,
            json={
                "name": "Browser Router",
                "hostname": "openwrt-browser",
                "model": "CI OpenWrt",
                "firmware": "OpenWrt browser fixture",
            },
        )
        provision.raise_for_status()
        device_id = provision.json()["device_id"]
        agent_headers = {"Authorization": f"Bearer {provision.json()['device_token']}"}
        capabilities = {
            "agent.update": True,
            "agent.set_interval": True,
            "agent.rollback": True,
            "diagnostics.check_server": True,
            "network.read": True,
            "network.interface_restart": True,
            "network.restart": True,
            "network.wan.configure": True,
            "network.lan.configure": True,
            "clients.read": True,
            "clients.block": True,
            "dhcp.set_lease": True,
            "dhcp.delete_lease": True,
            "dhcp.configure": True,
            "dns.configure": True,
            "firewall.port_forward": True,
            "system.reboot": True,
            "system.set_hostname": True,
            "system.restart_service": True,
            "system.set_timezone": True,
            "system.set_ntp": True,
            "wifi.enable": True,
            "wifi.disable": True,
            "wifi.set_ssid": True,
            "wifi.set_password": True,
            "wifi.set_channel": True,
            "wifi.set_country": True,
            "wifi.guest": True,
        }
        telemetry = client.post(
            "/api/v1/agent/telemetry",
            headers=agent_headers,
            json={
                "device_id": device_id,
                "telemetry": {
                    "agent": {
                        "version": "0.3.0",
                        "status": "running",
                        "capabilities_version": 4,
                        "capabilities": capabilities,
                    },
                    "system": {
                        "hostname": "openwrt-browser",
                        "uptime": 86400,
                        "load": "0.12",
                        "memory": {"total_kb": 262144, "available_kb": 131072},
                        "services": {"network": "running", "dnsmasq": "running"},
                    },
                    "wifi": {
                        "available": True,
                        "radios": [
                            {
                                "id": "radio0",
                                "name": "radio0",
                                "up": True,
                                "band": "2g",
                                "channel": "6",
                                "interfaces": [
                                    {
                                        "id": "default_radio0",
                                        "ssid": "WrtMonitor CI",
                                        "enabled": True,
                                        "encryption": "sae-mixed",
                                    }
                                ],
                            }
                        ],
                    },
                    "network": {
                        "interfaces": [
                            {
                                "interface": "lan",
                                "up": True,
                                "proto": "static",
                                "device": "br-lan",
                                "ipv4-address": [{"address": "192.168.1.1"}],
                            },
                            {
                                "interface": "wan",
                                "up": True,
                                "proto": "dhcp",
                                "device": "eth0",
                            },
                        ]
                    },
                    "clients": {
                        "dhcp": {
                            "leases": [
                                {
                                    "mac": "00:11:22:33:44:55",
                                    "ip": "192.168.1.10",
                                    "hostname": "test-client",
                                }
                            ]
                        }
                    },
                },
            },
        )
        telemetry.raise_for_status()
        return device_id


def assert_page(page: Page, path: str, screenshot_name: str) -> None:
    response = page.goto(f"{BASE_URL}{path}", wait_until="networkidle")
    assert response is not None and response.ok, (
        f"{path}: HTTP {response.status if response else 'none'}"
    )
    assert "Internal Server Error" not in page.locator("body").inner_text()
    overflow = page.evaluate(
        "document.documentElement.scrollWidth - document.documentElement.clientWidth"
    )
    assert overflow <= 1, f"{path}: horizontal overflow {overflow}px"
    page.screenshot(path=str(ARTIFACTS / screenshot_name), full_page=True)


def run() -> None:
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    device_id = prepare_router()
    with sync_playwright() as playwright:
        for name, viewport in (
            ("desktop", {"width": 1440, "height": 900}),
            ("mobile", {"width": 390, "height": 844}),
        ):
            browser = playwright.chromium.launch()
            page = browser.new_page(viewport=viewport)
            page.goto(f"{BASE_URL}/login")
            page.locator('input[name="username"]').fill(USERNAME)
            page.locator('input[name="password"]').fill(PASSWORD)
            page.locator('button[type="submit"]').click()
            page.wait_for_url("**/devices")
            assert_page(page, "/devices", f"{name}-devices.png")
            for section in (
                "overview",
                "network",
                "clients",
                "wifi",
                "system",
                "management",
            ):
                assert_page(
                    page,
                    f"/devices/{device_id}?section={section}",
                    f"{name}-{section}.png",
                )
            browser.close()


if __name__ == "__main__":
    run()
