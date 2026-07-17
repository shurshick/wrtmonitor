from __future__ import annotations

import os
import time
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
            "config.transaction": True,
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
            "clients.policy": True,
            "qos.sqm": True,
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
            "telemetry.wifi.stations": True,
            "wifi.radio.configure": True,
            "wifi.manage_ssid": True,
            "wifi.schedule": True,
            "wifi.roaming": True,
            "wifi.mesh": True,
            "network.ipv6.configure": True,
            "network.multiwan.configure": True,
            "network.routes.configure": True,
            "network.ddns.configure": True,
            "firewall.zones.configure": True,
            "firewall.rules.configure": True,
            "firewall.upnp.configure": True,
            "telemetry.perimeter": True,
            "vpn.wireguard.read": True,
            "vpn.wireguard.configure": True,
            "vpn.openvpn.read": True,
            "vpn.openvpn.configure": True,
            "vpn.policy.read": True,
            "vpn.policy.configure": True,
            "telemetry.vpn": True,
            "maintenance.packages.read": True,
            "maintenance.packages.write": True,
            "maintenance.backup": True,
            "maintenance.sysupgrade.check": True,
            "maintenance.sysupgrade.apply": True,
            "maintenance.logs": True,
            "maintenance.processes": True,
            "maintenance.cron": True,
            "maintenance.diagnostics.bundle": True,
            "maintenance.recovery": True,
            "telemetry.maintenance": True,
        }
        for sample in range(8):
            history_sample = client.post(
                "/api/v1/agent/telemetry",
                headers=agent_headers,
                json={
                    "device_id": device_id,
                    "telemetry": {
                        "system": {
                            "uptime": 86320 + sample * 10,
                            "load": str(0.08 + sample * 0.02),
                            "memory": {
                                "total_kb": 262144,
                                "available_kb": 150000 - sample * 1200,
                            },
                        },
                        "traffic": {
                            "rx_bytes": 5_000_000 + sample * sample * 190_000,
                            "tx_bytes": 2_000_000 + sample * 135_000,
                        },
                        "clients": {"dhcp": {"leases": []}},
                    },
                },
            )
            history_sample.raise_for_status()
            time.sleep(0.02)
        telemetry = client.post(
            "/api/v1/agent/telemetry",
            headers=agent_headers,
            json={
                "device_id": device_id,
                "telemetry": {
                    "agent": {
                        "version": "0.5.0",
                        "status": "running",
                        "capabilities_version": 10,
                        "capabilities": capabilities,
                    },
                    "system": {
                        "hostname": "openwrt-browser",
                        "uptime": 86400,
                        "load": "0.12",
                        "memory": {"total_kb": 262144, "available_kb": 131072},
                        "services": {"network": "running", "dnsmasq": "running"},
                    },
                    "traffic": {"rx_bytes": 16_000_000, "tx_bytes": 4_000_000},
                    "maintenance": {
                        "packages": {"installed": 143, "upgradable": 2},
                        "cron_entries": 1,
                        "recovery_mode": False,
                        "staged_firmware_sha256": "",
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
                        "stations": [
                            {
                                "interface": "wlan0",
                                "clients": {
                                    "00:11:22:33:44:55": {
                                        "signal": -52,
                                        "noise": -95,
                                        "tx_rate": "866 Mbit/s",
                                        "rx_rate": "650 Mbit/s",
                                    }
                                },
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
                    "vpn": {
                        "wireguard": {
                            "interfaces": [
                                {
                                    "name": "wg0",
                                    "public_key": "browser-public-key",
                                    "listen_port": 51820,
                                    "peers": [
                                        {
                                            "public_key": "phone-public-key",
                                            "endpoint": "198.51.100.10:51820",
                                            "latest_handshake": 1710000000,
                                            "rx_bytes": 1048576,
                                            "tx_bytes": 2097152,
                                        }
                                    ],
                                }
                            ]
                        },
                        "openvpn": {
                            "service": "running",
                            "clients": [{"name": "office", "enabled": True}],
                        },
                        "policy": {
                            "service": "running",
                            "policies": [
                                {
                                    "name": "tv-via-vpn",
                                    "interface": "wg0",
                                    "source": "192.168.1.50",
                                    "destination": "0.0.0.0/0",
                                }
                            ],
                        },
                    },
                    "clients": {
                        "dhcp": {
                            "leases": [
                                {
                                    "mac": "00:11:22:33:44:55",
                                    "ip": "192.168.1.10",
                                    "hostname": "test-client",
                                    "rx_bytes": 1048576,
                                    "tx_bytes": 524288,
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
    if page.locator("#traffic-chart").count():
        page.wait_for_function(
            "document.querySelector('#traffic-chart').width > 0 && document.querySelector('#traffic-chart').height > 0"
        )
        dimensions = page.locator("#traffic-chart").evaluate(
            "canvas => ({width: canvas.width, height: canvas.height})"
        )
        assert dimensions["width"] >= 320 and dimensions["height"] >= 170
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
            assert_page(page, "/account", f"{name}-account.png")
            for section in (
                "overview",
                "internet",
                "clients",
                "wifi",
                "rules",
                "vpn",
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
