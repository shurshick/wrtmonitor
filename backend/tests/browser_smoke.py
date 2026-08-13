from __future__ import annotations

import os
import time
import base64
import json
import threading
from pathlib import Path

import httpx
from playwright.sync_api import Page, sync_playwright


BASE_URL = os.getenv("WRTMONITOR_BROWSER_BASE_URL", "http://127.0.0.1:8090")
ARTIFACTS = Path(os.getenv("WRTMONITOR_BROWSER_ARTIFACTS", "artifacts/browser"))
USERNAME = "browser@example.com"
PASSWORD = "browser-test-password"


def prepare_router() -> tuple[str, str]:
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
            "agent.ssh_session": True,
            "diagnostics.check_server": True,
            "network.read": True,
            "network.interface_restart": True,
            "network.restart": True,
            "network.wan.configure": True,
            "network.lan.configure": True,
            "clients.read": True,
            "clients.block": True,
            "clients.policy": True,
            "clients.shaping": True,
            "qos.sqm": True,
            "dhcp.set_lease": True,
            "dhcp.delete_lease": True,
            "dhcp.configure": True,
            "dns.configure": True,
            "dns.encrypted.install": True,
            "dns.dot.configure": True,
            "dns.doh.configure": True,
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
            "network.segments.configure": True,
            "network.vlan.configure": True,
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
                        "schema_version": 2,
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
                    "schema_version": 2,
                    "agent": {
                        "version": "0.5.0",
                        "status": "running",
                        "capabilities_version": 10,
                        "capabilities": capabilities,
                    },
                    "hardware": {
                        "model": "WrtMonitor CI Router",
                        "board_name": "wrtmonitor,ci-router",
                        "compatible": ["wrtmonitor,ci-router"],
                        "target": "mediatek/filogic",
                        "package_arch": "aarch64_cortex-a53",
                        "architecture": "aarch64",
                    },
                    "cpu": {
                        "model": "Cortex-A53",
                        "architecture": "aarch64",
                        "cores": 2,
                        "current_khz": 1_000_000,
                        "max_khz": 1_300_000,
                    },
                    "thermal": {
                        "available": True,
                        "state": "observed",
                        "sensors": [
                            {
                                "id": "thermal_zone0",
                                "subsystem": "thermal",
                                "type": "cpu-thermal",
                                "label": "cpu-thermal",
                                "milli_celsius": 61_000,
                                "warning_milli_celsius": 85_000,
                                "critical_milli_celsius": 105_000,
                            },
                            {
                                "id": "hwmon1_temp1",
                                "subsystem": "hwmon",
                                "type": "mt7915_phy0",
                                "label": "mt7915 phy0",
                                "milli_celsius": 46_000,
                                "warning_milli_celsius": None,
                                "critical_milli_celsius": None,
                            },
                        ],
                        "throttling": {"state": "unsupported", "active": None},
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
                        "services": [
                            {
                                "name": name,
                                "running": name not in {"dropbear", "uhttpd"},
                                "enabled": name not in {"cron", "uhttpd"},
                            }
                            for name in (
                                "boot",
                                "cron",
                                "dnsmasq",
                                "done",
                                "dropbear",
                                "firewall",
                                "gpio_switch",
                                "led",
                                "log",
                                "network",
                                "odhcpd",
                                "rpcd",
                                "sysctl",
                                "sysfixtime",
                                "sysntpd",
                                "system",
                                "uhttpd",
                                "umount",
                                "urandom_seed",
                                "wrtmonitor",
                            )
                        ],
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
                                "configured_enabled": True,
                                "schedule": {
                                    "enabled": False,
                                    "weekdays": [],
                                    "start": "00:00",
                                    "stop": "00:00",
                                    "active_now": False,
                                    "base_enabled": True,
                                    "effective_enabled": True,
                                },
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
                                "configured_enabled": False,
                                "schedule": {
                                    "enabled": True,
                                    "weekdays": ["mon", "fri"],
                                    "start": "09:15",
                                    "stop": "22:45",
                                    "active_now": False,
                                    "base_enabled": False,
                                    "effective_enabled": False,
                                },
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
                    "network_devices": {
                        "eth0": {
                            "carrier": True,
                            "operstate": "up",
                            "mtu": 1500,
                            "macaddr": "02:00:00:00:00:01",
                            "speed_mbps": 2500,
                            "duplex": "full",
                            "rx_bytes": 16000000,
                            "tx_bytes": 4000000,
                            "rx_packets": 12000,
                            "tx_packets": 8000,
                            "rx_errors": 0,
                            "tx_errors": 0,
                            "rx_dropped": 1,
                            "tx_dropped": 0,
                        }
                    },
                    "network": {
                        "interfaces": [
                            {
                                "interface": "lan",
                                "up": True,
                                "proto": "static",
                                "device": "br-lan",
                                "ipv4-address": [{"address": "192.168.1.1"}],
                                "ipv6": ["fd42:1234::1/64"],
                                "ip6assign": "64",
                                "ip6hint": "0",
                            },
                            {
                                "interface": "wan",
                                "up": True,
                                "proto": "dhcp",
                                "device": "eth0",
                            },
                        ],
                        "topology": {
                            "segments": [
                                {
                                    "name": "lan",
                                    "proto": "static",
                                    "device": "br-lan",
                                    "bridge_section": "br_lan",
                                    "ip_address": "192.168.1.1",
                                    "netmask": "255.255.255.0",
                                    "policy": "trusted",
                                    "enabled": True,
                                    "dhcp": {
                                        "enabled": True,
                                        "start": "100",
                                        "limit": "150",
                                        "leasetime": "12h",
                                    },
                                }
                            ],
                            "bridges": [
                                {
                                    "section": "br_lan",
                                    "name": "br-lan",
                                    "ports": ["lan1", "lan2"],
                                    "stp": False,
                                    "igmp_snooping": True,
                                    "vlan_filtering": True,
                                }
                            ],
                            "vlans": [
                                {
                                    "section": "vlan10",
                                    "device": "br-lan",
                                    "vlan_id": 10,
                                    "ports": ["lan1:u*", "lan2:t"],
                                }
                            ],
                        },
                        "dns_privacy": {
                            "dot": {
                                "installed": True,
                                "running": True,
                                "provider": "cloudflare-dns.com",
                            },
                            "doh": {
                                "installed": True,
                                "running": False,
                                "resolver_url": "https://dns.quad9.net/dns-query",
                            },
                        },
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
                            ],
                            "pools": [
                                {
                                    "interface": "lan",
                                    "start": 100,
                                    "limit": 150,
                                    "leasetime": "12h",
                                    "enabled": True,
                                    "ra": "server",
                                    "dhcpv6": "server",
                                    "ndp": "disabled",
                                    "ra_management": "1",
                                }
                            ],
                        },
                        "traffic": {"available": True, "status": "ready"},
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
        return device_id, provision.json()["device_token"]


def terminal_agent_roundtrip(device_token: str, marker: str, errors: list[str]) -> None:
    try:
        headers = {"Authorization": f"Bearer {device_token}"}
        with httpx.Client(base_url=BASE_URL, timeout=35) as client:
            command = None
            for _ in range(6):
                commands = client.get(
                    "/api/v1/agent/commands", params={"wait": 5}, headers=headers
                ).json()
                command = next(
                    (item for item in commands if item["type"] == "agent.ssh_session"),
                    None,
                )
                if command:
                    break
            if command is None:
                raise AssertionError("browser did not enqueue terminal command")
            session_id = command["payload"]["session_id"]
            client.post(
                f"/api/v1/agent/commands/{command['id']}/result",
                headers=headers,
                json={"status": "running", "result": {}},
            ).raise_for_status()
            client.post(
                f"/api/v1/agent/terminal/sessions/{session_id}/status",
                headers=headers,
                json={"status": "connected"},
            ).raise_for_status()
            received = bytearray()
            cursor = 0
            for _ in range(120):
                response = client.get(
                    f"/api/v1/agent/terminal/sessions/{session_id}/down",
                    params={"after": cursor, "wait_seconds": 5},
                    headers=headers,
                )
                response.raise_for_status()
                for line in response.text.splitlines():
                    frame = json.loads(line)
                    cursor = max(cursor, int(frame.get("id") or 0))
                    if frame.get("type") == "data":
                        received.extend(base64.b64decode(frame["data"]))
                if marker.encode() in received:
                    break
            else:
                raise AssertionError("browser input did not reach terminal broker")
            output = f"PTY E2E OK: {marker}\r\n".encode()
            client.put(
                f"/api/v1/agent/terminal/sessions/{session_id}/up",
                headers=headers,
                content=output,
            ).raise_for_status()
            client.post(
                f"/api/v1/agent/terminal/sessions/{session_id}/status",
                headers=headers,
                json={"status": "closed", "reason": "browser E2E complete"},
            ).raise_for_status()
            client.post(
                f"/api/v1/agent/commands/{command['id']}/result",
                headers=headers,
                json={
                    "status": "success",
                    "result": {
                        "status": "ssh_started",
                        "session_id": session_id,
                    },
                },
            ).raise_for_status()
    except Exception as exc:  # pragma: no cover - reported in the browser job
        errors.append(str(exc))


def assert_page(page: Page, path: str, screenshot_name: str) -> None:
    # Device pages keep an EventSource open, so networkidle is never reached.
    response = page.goto(f"{BASE_URL}{path}", wait_until="domcontentloaded")
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
    device_id, device_token = prepare_router()
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
            page.evaluate("localStorage.setItem('wrtmonitor-theme', 'dark')")
            page.reload(wait_until="networkidle")
            assert page.locator("html").get_attribute("data-theme") == "dark"
            page.locator("[data-theme-toggle]").click()
            assert page.locator("html").get_attribute("data-theme") == "light"
            page.screenshot(
                path=str(ARTIFACTS / f"{name}-devices-light.png"), full_page=True
            )
            assert_page(page, "/account", f"{name}-account.png")
            assert page.locator("html").get_attribute("data-theme") == "light"
            page.locator("[data-theme-toggle]").click()
            assert page.locator("html").get_attribute("data-theme") == "dark"
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
            assert_page(page, "/events", f"{name}-events.png")
            assert page.locator(".event-item").count() >= 1
            assert page.get_by_text("Правила уведомлений", exact=True).count() == 1
            assert page.get_by_text("Автоматизация", exact=True).count() == 1
            for section in (
                "overview",
                "internet",
                "clients",
                "wifi",
                "rules",
                "vpn",
                "system",
                "hardware",
                "management",
                "terminal",
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
                if section == "internet":
                    page.get_by_text(
                        "Физические сетевые устройства", exact=True
                    ).click()
                    assert (
                        "2500 Мбит/с" in page.locator(".device-port-list").inner_text()
                    )
                    page.get_by_text("Шифрованный DNS", exact=True).click()
                    assert (
                        "DNS over TLS"
                        in page.locator(".encrypted-dns-grid").inner_text()
                    )
                    page.get_by_text("Подключение к интернету", exact=True).click()
                    wan = page.locator("[data-wan-form]")
                    wan.locator("[data-wan-protocol]").select_option("dhcp")
                    assert wan.locator('[data-wan-fields="static"]').is_hidden()
                    wan.locator("[data-wan-protocol]").select_option("pppoe")
                    assert wan.locator('[data-wan-fields="pppoe"]').is_visible()
                if section == "hardware":
                    assert (
                        page.get_by_text("Автоматическое изучение", exact=True).count()
                        == 1
                    )
                    assert (
                        page.get_by_text("Температурные датчики", exact=True).count()
                        == 1
                    )
                    assert "61.0 °C" in page.locator(".sensor-grid").inner_text()
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
                    assert (
                        page.locator('[data-wifi-field="enabled"]').input_value()
                        == "false"
                    )
                    schedule = page.locator("[data-wifi-schedule-form]")
                    schedule.locator("[data-wifi-schedule-radio]").select_option(
                        "radio1"
                    )
                    assert (
                        schedule.locator(
                            '[data-wifi-schedule-field="enabled"]'
                        ).input_value()
                        == "true"
                    )
                    assert (
                        schedule.locator(
                            '[data-wifi-schedule-field="start"]'
                        ).input_value()
                        == "09:15"
                    )
                    schedule.locator("[data-wifi-schedule-radio]").select_option(
                        "radio0"
                    )
                    assert (
                        schedule.locator(
                            '[data-wifi-schedule-field="enabled"]'
                        ).input_value()
                        == "false"
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
                    preset = client_row.locator("[data-client-preset]")
                    assert preset.count() == 1
                    assert preset.locator("option").all_text_contents() == [
                        "Свои настройки",
                        "Без ограничений",
                        "Ребёнок",
                        "Гость",
                        "Умное устройство",
                    ]
                    preset.select_option("guest")
                    assert (
                        client_row.locator('select[name="download_kbps"]').input_value()
                        == "25000"
                    )
                    assert (
                        client_row.locator('select[name="upload_kbps"]').input_value()
                        == "10000"
                    )
                    assert client_row.locator(".client-quick-actions").count() == 1
                    assert (
                        client_row.locator(
                            '.client-quick-actions input[name="preserve_profile_policy"]'
                        ).input_value()
                        == "true"
                    )
                    assert "Закрепить 192.168.1.10" in client_row.inner_text()
                    assert page.locator(".client-address-panel").count() == 1
                    ipv6_panel = (
                        page.locator("details.settings-panel")
                        .filter(has_text="IPv6, RA и DHCPv6")
                        .first
                    )
                    assert ipv6_panel.count() == 1
                    ipv6_panel.locator(":scope > summary").click()
                    assert (
                        ipv6_panel.locator('select[name="limit"]').input_value() == "64"
                    )
                    assert (
                        ipv6_panel.locator('select[name="protocol"]').input_value()
                        == "server"
                    )
                    assert (
                        ipv6_panel.locator('select[name="gateway"]').input_value()
                        == "server"
                    )
                    assert "fd42:1234::1/64" in ipv6_panel.inner_text()
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
                    if name == "desktop":
                        compact_cards = [
                            page.locator(".maintenance-card")
                            .filter(has_text=title)
                            .first.bounding_box()
                            for title in (
                                "Журналы и процессы",
                                "Автоматизация",
                                "Диагностический архив",
                            )
                        ]
                        assert all(box is not None for box in compact_cards)
                        assert (
                            max(box["y"] for box in compact_cards)
                            - min(box["y"] for box in compact_cards)
                            < 30
                        )
                    services = page.locator(".service-list-scroll")
                    assert services.count() == 1
                    assert (
                        services.evaluate("node => getComputedStyle(node).overflowY")
                        == "auto"
                    )
                    assert (
                        services.evaluate("node => getComputedStyle(node).maxHeight")
                        == "430px"
                    )
                    assert services.evaluate(
                        "node => node.scrollHeight > node.clientHeight"
                    )
                    assert page.get_by_text("Обновить каталог", exact=True).count() == 1
                    updates = page.locator("details.package-updates")
                    assert updates.count() == 1
                    assert updates.get_attribute("open") is None
                    updates.locator(":scope > summary").click()
                    assert updates.get_attribute("open") is not None
                    assert (
                        updates.locator(".package-list--updates").evaluate(
                            "node => getComputedStyle(node).overflowY"
                        )
                        == "auto"
                    )
                    assert (
                        page.get_by_text("Создать резервную копию", exact=True).count()
                        == 1
                    )
                    installed = page.locator("details.inline-details").filter(
                        has_text="Установленные пакеты"
                    )
                    installed.locator(":scope > summary").click()
                    package_search = installed.locator("[data-package-search]")
                    package_search.fill("tcpdump")
                    assert installed.locator(
                        '[data-package-name="tcpdump-mini"]'
                    ).is_visible()
                    assert installed.locator(
                        '[data-package-name="busybox"]'
                    ).is_hidden()
                    journal = page.locator("[data-command-journal]")
                    interval_input = page.locator('input[name="interval_seconds"]')
                    interval_input.fill("17")
                    page.locator('[data-command-page]:has-text("Дальше")').click()
                    page.wait_for_url("**command_page=2**")
                    page.locator(
                        "[data-command-journal] .command-pagination nav span"
                    ).filter(has_text="2 /").wait_for()
                    assert "command_page=2" in page.url
                    assert journal.count() == 1
                    assert interval_input.input_value() == "17"
                    page.screenshot(
                        path=str(ARTIFACTS / f"{name}-management-page2.png"),
                        full_page=True,
                    )
            if name == "desktop":
                marker = "wrtmonitor-browser-terminal-roundtrip"
                errors: list[str] = []
                worker = threading.Thread(
                    target=terminal_agent_roundtrip,
                    args=(device_token, marker, errors),
                    daemon=True,
                )
                worker.start()
                page.goto(
                    f"{BASE_URL}/devices/{device_id}?section=terminal",
                    wait_until="domcontentloaded",
                )
                page.locator("#btn-terminal-connect").click()
                terminal_input = page.locator(".xterm-helper-textarea")
                terminal_input.wait_for(state="attached")
                deadline = time.monotonic() + 30
                terminal_state = ""
                while time.monotonic() < deadline and not errors:
                    terminal_state = (
                        page.locator("[data-terminal-device]").get_attribute(
                            "data-terminal-state"
                        )
                        or ""
                    )
                    if terminal_state == "connected":
                        break
                    time.sleep(0.1)
                assert not errors, errors[0]
                assert terminal_state == "connected", (
                    f"terminal did not connect; state={terminal_state}"
                )
                assert page.evaluate(
                    """
                    () => document.querySelector('[data-terminal-device]')
                      .wrtmonitorTerminal.options.minimumContrastRatio >= 7
                    """
                ), "terminal contrast guard is disabled"
                terminal_input.evaluate("node => node.focus()")
                page.keyboard.type(marker)
                page.keyboard.press("Enter")
                page.wait_for_function(
                    """expected => {
                      const terminal = document.querySelector('[data-terminal-device]').wrtmonitorTerminal;
                      if (!terminal) return false;
                      const buffer = terminal.buffer.active;
                      let text = '';
                      for (let index = 0; index < buffer.length; index += 1) {
                        text += buffer.getLine(index)?.translateToString(true) || '';
                      }
                      return text.includes(expected);
                    }""",
                    arg=f"PTY E2E OK: {marker}",
                    timeout=30000,
                )
                worker.join(timeout=10)
                assert not worker.is_alive(), "terminal agent fixture did not finish"
                assert not errors, errors[0]
                page.screenshot(
                    path=str(ARTIFACTS / "desktop-terminal-connected.png"),
                    full_page=True,
                )
            browser.close()


if __name__ == "__main__":
    run()
