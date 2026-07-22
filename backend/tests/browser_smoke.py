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
                        "packages": {
                            "manager": "apk",
                            "installed": 143,
                            "upgradable": 2,
                            "installed_items": [
                                {"name": "tcpdump-mini", "version": "4.99.5"},
                                {"name": "busybox", "version": "1.36.1"},
                            ],
                            "upgradable_items": [
                                {
                                    "name": "tcpdump-mini",
                                    "current_version": "4.99.4",
                                    "available_version": "4.99.5",
                                }
                            ],
                        },
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
                                "country": "RU",
                                "htmode": "HT40",
                                "txpower": 18,
                                "interfaces": [
                                    {
                                        "id": "default_radio0",
                                        "ssid": "WrtMonitor CI",
                                        "enabled": True,
                                        "encryption": "sae-mixed",
                                    }
                                ],
                            },
                            {
                                "id": "radio1",
                                "name": "radio1",
                                "up": True,
                                "band": "5g",
                                "channel": "36",
                                "country": "DE",
                                "htmode": "VHT80",
                                "txpower": 23,
                                "interfaces": [
                                    {
                                        "id": "default_radio1",
                                        "ssid": "WrtMonitor CI 5G",
                                        "enabled": True,
                                        "encryption": "sae-mixed",
                                    }
                                ],
                            },
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
                    "perimeter": {
                        "firewall_zones": [
                            {
                                "section": "@zone[0]",
                                "name": "lan",
                                "networks": "lan",
                                "input": "ACCEPT",
                                "output": "ACCEPT",
                                "forward": "ACCEPT",
                                "masquerade": False,
                            },
                            {
                                "section": "@zone[1]",
                                "name": "wan",
                                "networks": "wan wan6",
                                "input": "REJECT",
                                "output": "ACCEPT",
                                "forward": "REJECT",
                                "masquerade": True,
                            },
                        ],
                        "firewall_forwardings": [
                            {"section": "@forwarding[0]", "src": "lan", "dest": "wan"}
                        ],
                        "firewall_rules": [
                            {
                                "section": "@rule[0]",
                                "name": "Allow-DHCP-Renew",
                                "src": "wan",
                                "dest": "",
                                "protocol": "udp",
                                "dest_port": "68",
                                "target": "ACCEPT",
                            }
                        ],
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
        for _ in range(7):
            command = client.post(
                f"/api/v1/devices/{device_id}/commands",
                headers=owner_headers,
                json={
                    "command_type": "agent.update",
                    "payload": {},
                    "confirmed": True,
                },
            )
            command.raise_for_status()
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
        assert dimensions["width"] >= 240 and dimensions["height"] >= 150
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
            page.locator('form[action="/account/mobile-pairing"] button').click()
            page.wait_for_load_state("networkidle")
            assert page.locator(".pairing-qr svg").count() == 1
            assert page.locator("[data-pairing-countdown]").count() == 1
            assert "pairing_token" not in page.content()
            overflow = page.evaluate(
                "document.documentElement.scrollWidth - document.documentElement.clientWidth"
            )
            assert overflow <= 1
            page.screenshot(
                path=str(ARTIFACTS / f"{name}-account-pairing.png"), full_page=True
            )
            with page.expect_navigation(url="**/account", wait_until="networkidle"):
                page.locator(
                    'form[action$="/revoke"] button', has_text="Отозвать QR"
                ).click()
            assert page.locator(".pairing-qr svg").count() == 0
            assert page.locator("[data-pairing-status]").text_content() == "отозван"
            assert "pairing_token" not in page.content()
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
                if section == "overview":
                    page.locator('[data-chart-range="24h"]').click()
                    page.locator(
                        '[data-live-monitor][data-loaded-range="24h"]'
                    ).wait_for()
                    assert "is-active" in (
                        page.locator('[data-chart-range="24h"]').get_attribute("class")
                        or ""
                    )
                    assert "24 часа" in page.locator("[data-chart-state]").inner_text()
                    page.locator('[data-chart-metric="memory"]').click()
                    assert "is-active" in (
                        page.locator('[data-chart-metric="memory"]').get_attribute(
                            "class"
                        )
                        or ""
                    )
                    assert "%" in page.locator("[data-chart-y]").first.inner_text()
                    page.screenshot(
                        path=str(ARTIFACTS / f"{name}-overview-24h-memory.png"),
                        full_page=True,
                    )
                if section == "wifi":
                    selector = page.locator("[data-wifi-radio-select]")
                    assert selector.count() == 1
                    selector.select_option("radio1")
                    assert (
                        page.locator('[data-wifi-field="channel"]').input_value()
                        == "36"
                    )
                    assert (
                        page.locator('[data-wifi-field="htmode"]').input_value()
                        == "VHT80"
                    )
                    assert (
                        page.locator('[data-wifi-field="country"]').input_value()
                        == "DE"
                    )
                    assert (
                        page.locator('[data-wifi-field="txpower"]').input_value()
                        == "23"
                    )
                    page.screenshot(
                        path=str(ARTIFACTS / f"{name}-wifi-5g.png"), full_page=True
                    )
                if section == "clients":
                    client_row = page.locator(".client-list-row").first
                    assert client_row.count() == 1
                    page.locator("[data-client-search]").fill("test-client")
                    assert client_row.is_visible()
                    page.locator('[data-client-filter="offline"]').click()
                    assert client_row.is_hidden()
                    assert page.locator("[data-client-empty]").is_visible()
                    page.locator('[data-client-filter="online"]').click()
                    assert client_row.is_visible()
                    client_row.locator("summary").click()
                    assert client_row.get_attribute("open") is not None
                    assert page.locator(".client-address-panel").count() == 1
                    page.screenshot(
                        path=str(ARTIFACTS / f"{name}-clients-expanded.png"),
                        full_page=True,
                    )
                if section == "rules":
                    for panel_title in ("Межсетевой экран", "Зоны и транзит"):
                        panel = (
                            page.locator("details.settings-panel")
                            .filter(has_text=panel_title)
                            .first
                        )
                        assert panel.count() == 1
                        assert panel.get_attribute("open") is None
                        panel.locator(":scope > summary").click()
                        assert panel.get_attribute("open") is not None
                    assert (
                        page.locator(
                            '.managed-record input[name="uci_section"]'
                        ).count()
                        >= 3
                    )
                    assert page.get_by_text("Удалить правило", exact=True).count() == 1
                if section == "system":
                    for panel_title in ("Идентификация", "Службы", "Дата и время"):
                        panel = (
                            page.locator("details.settings-panel")
                            .filter(has_text=panel_title)
                            .first
                        )
                        assert panel.count() == 1
                        assert panel.get_attribute("open") is None
                        panel.locator(":scope > summary").click()
                        assert panel.get_attribute("open") is not None
                if section == "management":
                    assert page.get_by_text("Обновить каталог", exact=True).count() == 1
                    assert (
                        page.get_by_text("Создать резервную копию", exact=True).count()
                        == 1
                    )
                    journal = page.locator("[data-command-journal]")
                    interval_input = page.locator('input[name="interval_seconds"]')
                    interval_input.fill("17")
                    page.locator('[data-command-page]:has-text("Дальше")').click()
                    page.locator(
                        "[data-command-journal] .command-pagination nav span",
                        has_text="2 / 2",
                    ).wait_for()
                    assert "command_page=2" in page.url
                    assert journal.count() == 1
                    assert interval_input.input_value() == "17"
                    page.screenshot(
                        path=str(ARTIFACTS / f"{name}-management-page2.png"),
                        full_page=True,
                    )
            browser.close()


if __name__ == "__main__":
    run()
