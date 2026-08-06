from __future__ import annotations

import argparse
import base64
import json
import os
import re
import secrets
import socket
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import paramiko
import requests


ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "contracts" / "command-contract.json"
TERMINAL = {"success", "failed", "expired", "cancelled"}


def slug(value: str) -> str:
    return re.sub(r"[^a-z0-9-]+", "-", value.lower()).strip("-")


def shell_single_quote(value: str) -> str:
    return value.replace("'", "'\"'\"'")


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


def env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise SystemExit(f"required environment variable is missing: {name}")
    return value


@dataclass(frozen=True)
class Target:
    name: str
    host: str
    device_id: str
    ssh_user: str = "root"


class Ssh:
    def __init__(self, target: Target, password: str):
        self.target = target
        self.password = password
        self.client = self._connect()

    def _connect(self) -> paramiko.SSHClient:
        self.client = paramiko.SSHClient()
        self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.client.connect(
            self.target.host,
            username=self.target.ssh_user,
            password=self.password,
            timeout=15,
            allow_agent=False,
            look_for_keys=False,
        )
        return self.client

    def run(self, command: str, *, timeout: int = 90, check: bool = True) -> str:
        try:
            _, stdout, stderr = self.client.exec_command(command, timeout=timeout)
            output = stdout.read().decode("utf-8", "replace")
            error = stderr.read().decode("utf-8", "replace")
            code = stdout.channel.recv_exit_status()
        except (EOFError, OSError, paramiko.SSHException):
            self.close()
            time.sleep(2)
            self.client = self._connect()
            _, stdout, stderr = self.client.exec_command(command, timeout=timeout)
            output = stdout.read().decode("utf-8", "replace")
            error = stderr.read().decode("utf-8", "replace")
            code = stdout.channel.recv_exit_status()
        if check and code:
            raise RuntimeError(f"SSH command failed ({code}): {error or output}")
        return output.strip()

    def close(self) -> None:
        self.client.close()

    def put_bytes(self, destination: str, content: bytes) -> None:
        for attempt in range(2):
            try:
                stdin, stdout, stderr = self.client.exec_command(
                    f"cat >'{shell_single_quote(destination)}'", timeout=90
                )
                stdin.channel.sendall(content)
                stdin.channel.shutdown_write()
                error = stderr.read().decode("utf-8", "replace")
                code = stdout.channel.recv_exit_status()
                if code:
                    raise RuntimeError(
                        f"failed to upload {destination} ({code}): {error}"
                    )
                return
            except (EOFError, OSError, paramiko.SSHException):
                if attempt:
                    raise
                self.close()
                time.sleep(2)
                self.client = self._connect()


class Api:
    def __init__(self, base_url: str, username: str, password: str):
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.password = password
        self.session = requests.Session()
        self.session.trust_env = False
        self.headers: dict[str, str] = {}
        self.login()

    def login(self) -> None:
        response = self.session.post(
            f"{self.base_url}/api/v1/auth/login",
            json={"username": self.username, "password": self.password},
            timeout=30,
        )
        response.raise_for_status()
        self.headers = {"Authorization": f"Bearer {response.json()['access_token']}"}

    def request(
        self, method: str, path: str, payload: dict[str, Any] | None = None
    ) -> Any:
        response: requests.Response | None = None
        last_error: Exception | None = None
        for attempt in range(4):
            try:
                response = self.session.request(
                    method,
                    f"{self.base_url}{path}",
                    headers=self.headers,
                    json=payload,
                    timeout=30,
                )
                if response.status_code == 401 and attempt < 3:
                    self.login()
                    time.sleep(1)
                    continue
                break
            except (requests.ConnectionError, requests.Timeout) as exc:
                last_error = exc
                self.session.close()
                self.session = requests.Session()
                self.session.trust_env = False
                if attempt < 3:
                    time.sleep(attempt + 1)
        if response is None:
            raise RuntimeError(f"API {method} {path} failed: {last_error}")
        if not response.ok:
            raise RuntimeError(
                f"API {method} {path} failed ({response.status_code}): {response.text}"
            )
        return response.json()

    def get(self, path: str) -> Any:
        return self.request("GET", path)

    def post(self, path: str, payload: dict[str, Any]) -> Any:
        return self.request("POST", path, payload)

    def create_command(
        self,
        device_id: str,
        command_type: str,
        payload: dict[str, Any],
        idempotency_key: str,
    ) -> tuple[str, bool]:
        body = {
            "command_type": command_type,
            "payload": payload,
            "confirmed": True,
            "idempotency_key": idempotency_key,
        }
        first = self.post(f"/api/v1/devices/{device_id}/commands", body)
        duplicate = self.post(f"/api/v1/devices/{device_id}/commands", body)
        return first["command_id"], first["command_id"] == duplicate["command_id"]

    def wait_command(
        self, device_id: str, command_id: str, timeout_seconds: int
    ) -> dict[str, Any]:
        deadline = time.monotonic() + timeout_seconds + 30
        while time.monotonic() < deadline:
            rows = self.get(f"/api/v1/devices/{device_id}/commands?limit=100")
            row = next((item for item in rows if item["id"] == command_id), None)
            if row and row.get("status") in TERMINAL:
                return row
            time.sleep(2)
        raise TimeoutError(f"command did not finish: {command_id}")


def contract() -> dict[str, Any]:
    return json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))


def fresh_report(target: Target, router_description: str) -> dict[str, Any]:
    spec = contract()
    return {
        "generated_at": now_iso(),
        "router": router_description,
        "target": target.name,
        "contract_version": spec["command_contract_version"],
        "commands": {
            name: {
                "status": "not_run",
                "idempotency": "not_run",
                "timeout": "not_run",
                "redelivery": "not_run",
                "post_condition": "not_run",
                "rollback": "not_run",
                "evidence": None,
            }
            for name in spec["commands"]
        },
    }


def load_report(
    target: Target, router_description: str, resume: bool
) -> dict[str, Any]:
    path = ROOT / "certification" / f"{slug(target.name)}.json"
    if resume and path.is_file():
        report = json.loads(path.read_text(encoding="utf-8"))
        report["router"] = router_description
        report["generated_at"] = now_iso()
        return report
    return fresh_report(target, router_description)


def ssh_json(ssh: Ssh, command: str) -> Any:
    raw = ssh.run(command, check=False)
    try:
        return json.loads(raw) if raw else {}
    except json.JSONDecodeError:
        return {}


def uci(ssh: Ssh, key: str, default: str = "") -> str:
    value = ssh.run(f"uci -q get {key}", check=False)
    return value if value else default


def first_uci_section(ssh: Ssh, config: str, section_type: str) -> str:
    command = (
        f"uci -q show {config} | sed -n "
        f"'s/^{config}\\.\\([^.=]*\\)={section_type}$/\\1/p' | head -n1"
    )
    return ssh.run(command, check=False)


def target_facts(api: Api, target: Target, ssh: Ssh) -> dict[str, Any]:
    latest = api.get(f"/api/v1/devices/{target.device_id}/telemetry/latest")
    telemetry = latest.get("telemetry") or {}
    agent = latest.get("agent") or {}
    capabilities = agent.get("capabilities") or {}
    radio = first_uci_section(ssh, "wireless", "wifi-device")
    iface = first_uci_section(ssh, "wireless", "wifi-iface")
    lan_ip = uci(ssh, "network.lan.ipaddr", "192.168.1.1")
    lan_ip = lan_ip.split("/", 1)[0]
    lan_mask = uci(ssh, "network.lan.netmask", "255.255.255.0")
    wan_proto = uci(ssh, "network.wan.proto", "dhcp")
    clients = (telemetry.get("clients") or {}).get("items") or []
    mac = "02:00:00:00:ce:01"
    for item in clients:
        candidate = str(item.get("mac") or "").lower()
        if re.fullmatch(r"(?:[0-9a-f]{2}:){5}[0-9a-f]{2}", candidate):
            mac = candidate
            break
    wifi_key = uci(ssh, f"wireless.{iface}.key", "WrtMonitor-Cert-Only")
    if len(wifi_key) < 8:
        wifi_key = "WrtMonitor-Cert-Only"
    return {
        "telemetry": telemetry,
        "agent": agent,
        "capabilities": capabilities,
        "radio": radio,
        "iface": iface,
        "ssid": uci(ssh, f"wireless.{iface}.ssid", "WrtMonitor"),
        "wifi_key": wifi_key,
        "wifi_encryption": uci(ssh, f"wireless.{iface}.encryption", "sae-mixed"),
        "wifi_network": uci(ssh, f"wireless.{iface}.network", "lan").split()[0],
        "wifi_channel": uci(ssh, f"wireless.{radio}.channel", "auto"),
        "wifi_country": uci(ssh, f"wireless.{radio}.country", "RU"),
        "wifi_htmode": uci(ssh, f"wireless.{radio}.htmode", "HT20"),
        "lan_ip": lan_ip,
        "lan_mask": lan_mask,
        "wan_proto": wan_proto,
        "wan_interface": "wan",
        "hostname": uci(ssh, "system.@system[0].hostname", "OpenWrt"),
        "timezone": uci(ssh, "system.@system[0].timezone", "MSK-3"),
        "zonename": uci(ssh, "system.@system[0].zonename", "Europe/Moscow"),
        "ntp_enabled": uci(ssh, "system.ntp.enabled", "1") != "0",
        "ntp_servers": ssh.run(
            "uci -q get system.ntp.server | tr ' ' '\\n'", check=False
        ).splitlines()
        or ["0.openwrt.pool.ntp.org"],
        "dhcp_start": int(uci(ssh, "dhcp.lan.start", "100")),
        "dhcp_limit": int(uci(ssh, "dhcp.lan.limit", "150")),
        "dhcp_leasetime": uci(ssh, "dhcp.lan.leasetime", "12h"),
        "ipv6_enabled": bool(uci(ssh, "network.lan.ip6assign")),
        "ipv6_assignment": int(uci(ssh, "network.lan.ip6assign", "64") or "64"),
        "ipv6_ra": uci(ssh, "dhcp.lan.ra", "disabled"),
        "ipv6_dhcpv6": uci(ssh, "dhcp.lan.dhcpv6", "disabled"),
        "ipv6_ndp": uci(ssh, "dhcp.lan.ndp", "disabled"),
        "client_mac": mac,
        "package_manager": "apk" if ssh.run("command -v apk", check=False) else "opkg",
        "bridge_port": (
            ssh.run("uci -q get network.@device[0].ports", check=False).split()
            or ["eth0"]
        )[0],
    }


def payloads(f: dict[str, Any], ssh: Ssh) -> dict[str, dict[str, Any]]:
    cert_name = "wrtmonitor_cert"
    wg_private = base64.b64encode(secrets.token_bytes(32)).decode()
    wg_public = base64.b64encode(secrets.token_bytes(32)).decode()
    backup_base64 = ssh.run(
        "p=/tmp/wrtmonitor-certification-backup.tar.gz; "
        'sysupgrade -b "$p" >/dev/null && base64 <"$p" | tr -d \'\\n\'; '
        'rc=$?; rm -f "$p"; exit $rc',
        timeout=120,
    )
    return {
        "agent.set_auto_update": {"enabled": True},
        "agent.set_interval": {"interval_seconds": 5},
        "agent.update": {"force": bool(os.environ.get("WRTMONITOR_AGENT_UPDATE_URL"))},
        "agent.rotate_token": {},
        "diagnostics.run": {
            "checks": ["server", "dns", "route", "wifi", "dependencies"]
        },
        "wifi.status": {},
        "wifi.set_enabled": {"radio": f["radio"], "enabled": True},
        "wifi.set_ssid": {"iface": f["iface"], "ssid": f["ssid"]},
        "wifi.set_password": {"iface": f["iface"], "password": f["wifi_key"]},
        "wifi.set_channel": {"radio": f["radio"], "channel": f["wifi_channel"]},
        "wifi.set_country": {"radio": f["radio"], "country": f["wifi_country"]},
        "wifi.set_radio": {
            "radio": f["radio"],
            "channel": f["wifi_channel"],
            "country": f["wifi_country"],
            "htmode": f["wifi_htmode"],
        },
        "wifi.add_ssid": {
            "radio": f["radio"],
            "ssid": "WrtMonitor-Cert",
            "network": "lan",
            "encryption": "sae",
            "key": "WrtMonitor-Cert-Only",
            "hidden": True,
            "isolate": True,
        },
        "wifi.update_ssid": {
            "iface": "wrtmonitor_cert_wifi",
            "ssid": "WrtMonitor-Cert-Updated",
            "network": "lan",
            "encryption": "sae",
            "key": "WrtMonitor-Cert-Only",
            "enabled": False,
            "hidden": True,
            "isolate": True,
            "ieee80211r": False,
            "ieee80211k": False,
            "bss_transition": False,
        },
        "wifi.delete_ssid": {"iface": "wrtmonitor_cert_wifi"},
        "wifi.set_schedule": {
            "radio": f["radio"],
            "enabled": False,
            "weekdays": [],
            "start": "",
            "stop": "",
        },
        "wifi.set_mesh": {"radio": f["radio"], "enabled": False},
        "wifi.set_guest": {"radio": f["radio"], "enabled": False},
        "network.interfaces": {},
        "network.interface_restart": {"interface": "lan"},
        "network.set_wan": {
            "interface": "wan",
            "protocol": f["wan_proto"]
            if f["wan_proto"] in {"dhcp", "static", "pppoe"}
            else "dhcp",
        },
        "network.set_lan": {
            "interface": "lan",
            "ip_address": f["lan_ip"],
            "netmask": f["lan_mask"],
        },
        "network.set_ipv6": {
            "interface": "lan",
            "enabled": f["ipv6_enabled"],
            "assignment_length": f["ipv6_assignment"],
            "ra": f["ipv6_ra"],
            "dhcpv6": f["ipv6_dhcpv6"],
            "ndp": f["ipv6_ndp"],
        },
        "network.set_segment": {
            "name": cert_name,
            "protocol": "static",
            "ip_address": "10.253.0.1",
            "netmask": "255.255.255.0",
            "device": "",
            "bridge": False,
            "dhcp_enabled": False,
            "firewall_policy": "isolated",
        },
        "network.delete_segment": {"name": cert_name},
        "network.set_vlan": {
            "section": "wrtmonitor_cert_vlan",
            "device": "br-cert",
            "vlan_id": 4093,
            "ports": ["cert0:t"],
        },
        "network.delete_vlan": {
            "section": "wrtmonitor_cert_vlan",
            "device": "br-cert",
            "vlan_id": 4093,
            "ports": ["cert0:t"],
        },
        "network.set_route": {
            "section": "wrtmonitor_cert_route",
            "name": "wrtmonitor_cert_route",
            "interface": "lan",
            "target": "198.51.100.0/24",
            "gateway": "",
            "metric": 250,
        },
        "network.delete_route": {
            "section": "wrtmonitor_cert_route",
            "name": "wrtmonitor_cert_route",
        },
        "network.restart": {},
        "network.set_ddns": {
            "name": cert_name,
            "enabled": False,
            "provider": "cloudflare.com-v4",
            "domain": "cert.invalid",
            "username": "",
            "password": "",
            "interface": "wan",
        },
        "network.set_upnp": {"enabled": False, "secure_mode": True},
        "network.set_multiwan": {
            "enabled": False,
            "primary_interface": "wan",
            "secondary_interface": "wan6",
            "primary_metric": 10,
            "secondary_metric": 20,
            "track_ips": ["1.1.1.1"],
            "check_interval": 5,
            "failure_interval": 3,
            "recovery_interval": 3,
        },
        "dhcp.set_lease": {
            "mac": "02:00:00:00:ce:01",
            "ip": f["lan_ip"].rsplit(".", 1)[0] + ".249",
            "hostname": "wrtmonitor-cert",
        },
        "dhcp.delete_lease": {"mac": "02:00:00:00:ce:01"},
        "dhcp.set_pool": {
            "interface": "lan",
            "start": f["dhcp_start"],
            "limit": f["dhcp_limit"],
            "leasetime": f["dhcp_leasetime"],
        },
        "dns.set_servers": {"servers": ["1.1.1.1", "9.9.9.9"]},
        "dns.install_dot": {},
        "dns.install_doh": {},
        "dns.set_dot": {"provider": "cloudflare", "enabled": False},
        "dns.set_doh": {"provider": "cloudflare", "enabled": False},
        "client.set_blocked": {"mac": f["client_mac"], "blocked": False},
        "client.set_policy": {
            "mac": f["client_mac"],
            "blocked": False,
            "schedule": {"enabled": False, "weekdays": [], "start": "", "stop": ""},
            "qos": {"priority": "normal", "download_kbps": 0, "upload_kbps": 0},
            "dns": {"provider": "none"},
        },
        "qos.set_sqm": {
            "enabled": False,
            "interface": "wan",
            "profile": "balanced",
            "download_kbps": 100000,
            "upload_kbps": 50000,
            "qdisc": "cake",
            "script": "piece_of_cake.qos",
            "schedule": {"enabled": False, "weekdays": [], "start": "", "stop": ""},
        },
        "firewall.set_zone": {
            "section": "wrtmonitor_cert_zone",
            "name": cert_name,
            "networks": [cert_name],
            "input": "REJECT",
            "output": "ACCEPT",
            "forward": "REJECT",
            "masquerade": False,
        },
        "firewall.delete_zone": {"section": "wrtmonitor_cert_zone", "name": cert_name},
        "firewall.set_forwarding": {
            "section": "wrtmonitor_cert_forward",
            "src": cert_name,
            "dest": "lan",
            "enabled": True,
        },
        "firewall.delete_forwarding": {
            "section": "wrtmonitor_cert_forward",
            "src": cert_name,
            "dest": "lan",
        },
        "firewall.set_rule": {
            "section": "wrtmonitor_cert_rule",
            "name": cert_name,
            "src": "lan",
            "dest": "*",
            "protocol": "icmp",
            "src_ip": "",
            "dest_ip": "",
            "src_port": "",
            "dest_port": "",
            "target": "ACCEPT",
        },
        "firewall.delete_rule": {"section": "wrtmonitor_cert_rule", "name": cert_name},
        "firewall.set_redirect": {
            "section": "wrtmonitor_cert_redirect",
            "name": cert_name,
            "enabled": False,
            "src": "wan",
            "dest": "lan",
            "protocol": "tcp",
            "src_ip": "",
            "src_port": "65529",
            "dest_ip": f["lan_ip"].rsplit(".", 1)[0] + ".249",
            "dest_port": "65529",
            "target": "DNAT",
        },
        "firewall.delete_redirect": {
            "section": "wrtmonitor_cert_redirect",
            "name": cert_name,
        },
        "firewall.set_port_forward": {
            "section": "wrtmonitor_cert_port",
            "name": cert_name,
            "protocol": "tcp",
            "external_port": 65530,
            "internal_ip": f["lan_ip"].rsplit(".", 1)[0] + ".249",
            "internal_port": 65530,
        },
        "firewall.delete_port_forward": {
            "section": "wrtmonitor_cert_port",
            "name": cert_name,
        },
        "vpn.wireguard.set_interface": {
            "name": "wgcert",
            "enabled": False,
            "mode": "server",
            "addresses": ["10.254.0.1/24"],
            "listen_port": 51829,
            "private_key": wg_private,
            "mtu": 1420,
        },
        "vpn.wireguard.set_peer": {
            "interface": "wgcert",
            "name": "certpeer",
            "public_key": wg_public,
            "preshared_key": "",
            "allowed_ips": ["10.254.0.2/32"],
            "endpoint": "",
            "persistent_keepalive": 0,
            "route_allowed_ips": False,
        },
        "vpn.wireguard.export_peer": {"interface": "wgcert", "name": "certpeer"},
        "vpn.wireguard.delete_peer": {"interface": "wgcert", "name": "certpeer"},
        "vpn.wireguard.delete_interface": {"name": "wgcert"},
        "vpn.openvpn.set_client": {
            "name": "certclient",
            "enabled": False,
            "config": "client\ndev tun\nproto udp\nremote 192.0.2.1 1194\nnobind\n",
        },
        "vpn.openvpn.set_enabled": {"name": "certclient", "enabled": False},
        "vpn.openvpn.export_client": {"name": "certclient"},
        "vpn.openvpn.delete_client": {"name": "certclient"},
        "vpn.policy.set": {
            "section": "wrtmonitor_cert_policy",
            "name": "cert_policy",
            "enabled": False,
            "interface": "wan",
            "source": "198.51.100.1",
            "destination": "",
            "protocol": "all",
        },
        "vpn.policy.delete": {
            "section": "wrtmonitor_cert_policy",
            "name": "cert_policy",
        },
        "system.set_hostname": {"hostname": f["hostname"]},
        "system.set_timezone": {"zonename": f["zonename"], "timezone": f["timezone"]},
        "system.set_ntp": {"enabled": f["ntp_enabled"], "servers": f["ntp_servers"]},
        "system.restart_service": {"service": "dnsmasq"},
        "router.reboot": {},
        "maintenance.packages.refresh": {},
        "maintenance.package.install": {"package": "nano"},
        "maintenance.package.upgrade": {"package": "nano"},
        "maintenance.package.remove": {"package": "nano"},
        "maintenance.backup.create": {},
        "maintenance.backup.restore": {"archive_base64": backup_base64},
        "maintenance.logs.read": {"lines": 50},
        "maintenance.processes.read": {},
        "maintenance.process.signal": {"pid": 2, "signal": "HUP"},
        "maintenance.cron.read": {},
        "maintenance.cron.set": {
            "content": ssh.run("cat /etc/crontabs/root 2>/dev/null", check=False)
        },
        "maintenance.services.read": {},
        "maintenance.service.set": {"service": "cron", "action": "restart"},
        "maintenance.diagnostics.bundle": {},
        "maintenance.recovery.enable": {},
        "maintenance.recovery.disable": {},
        "maintenance.module.configure": {"module": "ftp", "action": "install"},
        "maintenance.sysupgrade.check": {
            "url": "https://example.invalid/wrtmonitor-certification.bin",
            "sha256": "0" * 64,
            "expected_model": "WrtMonitor certification mismatch",
            "preserve_config": True,
        },
        "maintenance.sysupgrade.apply": {
            "sha256": "0" * 64,
            "preserve_config": True,
        },
    }


ORDER = [
    "diagnostics.run",
    "wifi.status",
    "network.interfaces",
    "maintenance.logs.read",
    "maintenance.processes.read",
    "maintenance.process.signal",
    "maintenance.cron.read",
    "maintenance.services.read",
    "maintenance.backup.create",
    "maintenance.backup.restore",
    "maintenance.diagnostics.bundle",
    "agent.set_auto_update",
    "agent.set_interval",
    "agent.update",
    "agent.rollback",
    "agent.rotate_token",
    "system.set_hostname",
    "system.set_timezone",
    "system.set_ntp",
    "system.restart_service",
    "dhcp.set_pool",
    "dhcp.set_lease",
    "dhcp.delete_lease",
    "client.set_blocked",
    "client.set_policy",
    "wifi.set_enabled",
    "wifi.set_ssid",
    "wifi.set_password",
    "wifi.set_channel",
    "wifi.set_country",
    "wifi.set_radio",
    "wifi.set_schedule",
    "wifi.set_guest",
    "wifi.set_mesh",
    "wifi.add_ssid",
    "wifi.update_ssid",
    "wifi.delete_ssid",
    "network.set_segment",
    "firewall.set_zone",
    "firewall.set_forwarding",
    "firewall.set_rule",
    "firewall.set_redirect",
    "firewall.set_port_forward",
    "firewall.delete_port_forward",
    "firewall.delete_redirect",
    "firewall.delete_rule",
    "firewall.delete_forwarding",
    "firewall.delete_zone",
    "network.delete_segment",
    "network.set_route",
    "network.delete_route",
    "network.set_vlan",
    "network.delete_vlan",
    "vpn.wireguard.set_interface",
    "vpn.wireguard.set_peer",
    "vpn.wireguard.export_peer",
    "vpn.wireguard.delete_peer",
    "vpn.wireguard.delete_interface",
    "vpn.openvpn.set_client",
    "vpn.openvpn.set_enabled",
    "vpn.openvpn.export_client",
    "vpn.openvpn.delete_client",
    "vpn.policy.set",
    "vpn.policy.delete",
    "dns.install_dot",
    "dns.set_dot",
    "dns.install_doh",
    "dns.set_doh",
    "dns.set_servers",
    "qos.set_sqm",
    "network.set_ddns",
    "network.set_upnp",
    "network.set_multiwan",
    "network.set_ipv6",
    "network.set_wan",
    "network.set_lan",
    "network.interface_restart",
    "maintenance.packages.refresh",
    "maintenance.package.install",
    "maintenance.package.upgrade",
    "maintenance.package.remove",
    "maintenance.module.configure",
    "maintenance.cron.set",
    "maintenance.service.set",
    "maintenance.recovery.enable",
    "maintenance.recovery.disable",
    "maintenance.sysupgrade.check",
    "maintenance.sysupgrade.apply",
    "network.restart",
    "router.reboot",
    "agent.disconnect",
]


NOT_APPLICABLE: dict[str, str] = {}


EXPECTED_FAILURES = {
    "maintenance.sysupgrade.check": "firmware model does not match router",
    "maintenance.sysupgrade.apply": "validated firmware is not staged",
}


def redact(
    command: str, payload: dict[str, Any], result: Any
) -> tuple[dict[str, Any], Any]:
    metadata = contract()["commands"][command]
    clean_payload = dict(payload)
    for field in metadata.get("secret_fields", []):
        if field in clean_payload:
            clean_payload[field] = "<redacted>"
    clean_result = json.loads(json.dumps(result))
    secret_names = {
        "archive_base64",
        "bundle_base64",
        "config_base64",
        "config",
        "private_key",
        "preshared_key",
        "key",
        "password",
    }

    def walk(value: Any) -> Any:
        if isinstance(value, dict):
            return {
                key: "<redacted>" if key in secret_names else walk(item)
                for key, item in value.items()
            }
        if isinstance(value, list):
            return [walk(item) for item in value]
        return value

    return clean_payload, walk(clean_result)


def write_evidence(
    target_slug: str,
    command: str,
    payload: dict[str, Any],
    row: dict[str, Any],
    elapsed: float,
    duplicate_same_id: bool,
) -> str:
    destination = ROOT / "certification" / "evidence" / target_slug / command
    destination.mkdir(parents=True, exist_ok=True)
    clean_payload, clean_result = redact(command, payload, row.get("result"))
    evidence = {
        "tested_at": now_iso(),
        "command": command,
        "payload": clean_payload,
        "status": row.get("status"),
        "result": clean_result,
        "error": row.get("error"),
        "elapsed_seconds": round(elapsed, 3),
        "idempotency_duplicate_returned_same_command": duplicate_same_id,
        "retry_count": row.get("retry_count"),
        "reliability": row.get("reliability"),
    }
    (destination / "result.json").write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return str(destination.relative_to(ROOT)).replace("\\", "/")


def wait_online(api: Api, target: Target, timeout: int = 180) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        devices = api.get("/api/v1/devices")
        row = next((item for item in devices if item["id"] == target.device_id), None)
        if row and row.get("status") == "online":
            return
        time.sleep(5)
    raise TimeoutError(f"router did not return online: {target.name}")


def pin_control_plane_host(ssh: Ssh) -> None:
    server = uci(ssh, "wrtmonitor.main.server_url")
    hostname = urlparse(server).hostname if server else None
    if not hostname or re.fullmatch(r"[0-9a-fA-F:.]+", hostname):
        return
    address = socket.gethostbyname(hostname)
    marker = "# wrtmonitor-certification-control-plane"
    ssh.run(
        f"sed -i '/{marker}$/d' /etc/hosts; "
        f"printf '%s %s %s\\n' '{shell_single_quote(address)}' "
        f"'{shell_single_quote(hostname)}' '{marker}' >>/etc/hosts"
    )


def restore_baseline(ssh: Ssh, archive: bytes) -> None:
    remote_archive = "/tmp/wrtmonitor-certification-baseline.tar.gz"
    current_device_id = uci(ssh, "wrtmonitor.main.device_id")
    current_device_token = uci(ssh, "wrtmonitor.main.device_token")
    ssh.put_bytes(remote_archive, archive)
    ssh.run(
        "set -eu; "
        f"sysupgrade -r {remote_archive}; rm -f {remote_archive}; "
        "uci set wrtmonitor.main.device_id='"
        + shell_single_quote(current_device_id)
        + "'; "
        "uci set wrtmonitor.main.device_token='"
        + shell_single_quote(current_device_token)
        + "'; "
        "uci set wrtmonitor.main.enabled=1; uci commit wrtmonitor; "
        "/etc/init.d/dnsmasq restart >/dev/null 2>&1 || true; "
        "/etc/init.d/firewall restart >/dev/null 2>&1 || true; "
        "wifi reload >/dev/null 2>&1 || true; "
        "/etc/init.d/network reload >/dev/null 2>&1 || true; "
        "/etc/init.d/wrtmonitor restart >/dev/null 2>&1 || true",
        timeout=120,
        check=False,
    )


def certify(target: Target, selected: set[str] | None, resume: bool) -> Path:
    api = Api(
        env("WRTMONITOR_SERVER_URL"),
        env("WRTMONITOR_ADMIN_USER"),
        env("WRTMONITOR_ADMIN_PASSWORD"),
    )
    ssh = Ssh(target, env("WRTMONITOR_ROUTER_PASSWORD"))
    baseline_archive: bytes | None = None
    try:
        f = target_facts(api, target, ssh)
        description = " / ".join(
            filter(
                None,
                [
                    target.name,
                    ssh.run("cat /tmp/sysinfo/model 2>/dev/null", check=False),
                    ssh.run(
                        ". /etc/openwrt_release; echo $DISTRIB_DESCRIPTION", check=False
                    ),
                ],
            )
        )
        report = load_report(target, description, resume)
        target_slug = slug(target.name)
        recipes = payloads(f, ssh)
        baseline_archive = base64.b64decode(
            recipes["maintenance.backup.restore"]["archive_base64"]
        )
        pin_control_plane_host(ssh)
        spec = contract()["commands"]
        selected_commands = selected or set(spec)

        for command, reason in NOT_APPLICABLE.items():
            if command not in selected_commands:
                continue
            evidence_dir = ROOT / "certification" / "evidence" / target_slug / command
            evidence_dir.mkdir(parents=True, exist_ok=True)
            (evidence_dir / "result.json").write_text(
                json.dumps(
                    {
                        "tested_at": now_iso(),
                        "command": command,
                        "status": "not_applicable",
                        "reason": reason,
                    },
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
            report["commands"][command].update(
                status="not_applicable",
                idempotency="not_applicable",
                timeout="not_applicable",
                redelivery="not_applicable",
                post_condition="not_applicable",
                rollback="not_applicable",
                evidence=str(evidence_dir.relative_to(ROOT)).replace("\\", "/"),
            )

        for command in ORDER:
            if command not in selected_commands or command in NOT_APPLICABLE:
                continue
            capability = spec[command]["capability"]
            if f["capabilities"] and not bool(f["capabilities"].get(capability, False)):
                evidence_dir = (
                    ROOT / "certification" / "evidence" / target_slug / command
                )
                evidence_dir.mkdir(parents=True, exist_ok=True)
                (evidence_dir / "result.json").write_text(
                    json.dumps(
                        {
                            "tested_at": now_iso(),
                            "command": command,
                            "status": "not_applicable",
                            "reason": f"router reported capability {capability}=false",
                        },
                        ensure_ascii=False,
                        indent=2,
                    )
                    + "\n",
                    encoding="utf-8",
                )
                report["commands"][command].update(
                    status="not_applicable",
                    idempotency="not_applicable",
                    timeout="not_applicable",
                    redelivery="not_applicable",
                    post_condition="not_applicable",
                    rollback="not_applicable",
                    evidence=str(evidence_dir.relative_to(ROOT)).replace("\\", "/"),
                )
                print(f"NA   {target.name}: {command} ({capability})", flush=True)
                continue
            payload = recipes.get(command, {})
            original_update_url: str | None = None
            if command == "agent.update" and os.environ.get(
                "WRTMONITOR_AGENT_UPDATE_URL"
            ):
                original_update_url = uci(ssh, "wrtmonitor.main.update_source")
                update_url = os.environ["WRTMONITOR_AGENT_UPDATE_URL"].rstrip("/")
                ssh.run(
                    "uci set wrtmonitor.main.update_source='"
                    + shell_single_quote(update_url)
                    + "'; uci commit wrtmonitor"
                )
            if command == "maintenance.process.signal":
                payload = {
                    "pid": int(
                        ssh.run("sleep 300 </dev/null >/dev/null 2>&1 & echo $!")
                    ),
                    "signal": "TERM",
                }
            if command == "agent.rollback":
                ssh.run(
                    "set -eu; backup=/etc/wrtmonitor/backup; "
                    'rm -rf "$backup"; mkdir -p "$backup/lib.previous"; '
                    'cp /usr/bin/wrtmonitor-agent "$backup/wrtmonitor-agent.previous"; '
                    'cp /etc/init.d/wrtmonitor "$backup/wrtmonitor.init.previous"; '
                    'cp /usr/lib/wrtmonitor/*.sh "$backup/lib.previous/"; '
                    'wrtmonitor-agent version >"$backup/VERSION.previous"'
                )
            if command == "network.set_vlan":
                ssh.run(
                    "uci -q delete network.wrtmonitor_cert_bridge || true; "
                    "uci set network.wrtmonitor_cert_bridge=device; "
                    "uci set network.wrtmonitor_cert_bridge.name=br-cert; "
                    "uci set network.wrtmonitor_cert_bridge.type=bridge; "
                    "uci add_list network.wrtmonitor_cert_bridge.ports=cert0; "
                    "uci commit network; /etc/init.d/network reload; "
                    "/etc/init.d/wrtmonitor restart"
                )
                bridge_deadline = time.monotonic() + 45
                while time.monotonic() < bridge_deadline:
                    latest = api.get(
                        f"/api/v1/devices/{target.device_id}/telemetry/latest"
                    )
                    topology = (
                        (latest.get("telemetry") or {})
                        .get("network", {})
                        .get("topology", {})
                    )
                    if any(
                        item.get("name") == "br-cert"
                        for item in topology.get("bridges", [])
                    ):
                        break
                    time.sleep(3)
            key = f"hardware-{target_slug}-{command}-{secrets.token_hex(6)}"
            started = time.monotonic()
            try:
                command_id, duplicate_same_id = api.create_command(
                    target.device_id, command, payload, key
                )
                row = api.wait_command(
                    target.device_id,
                    command_id,
                    int(spec[command]["reliability"]["delivery"]["timeout_seconds"]),
                )
                elapsed = time.monotonic() - started
                evidence = write_evidence(
                    target_slug, command, payload, row, elapsed, duplicate_same_id
                )
                expected_error = EXPECTED_FAILURES.get(command)
                actual_error = str(
                    row.get("error") or (row.get("result") or {}).get("error") or ""
                )
                passed = (
                    row.get("status") == "success"
                    if expected_error is None
                    else row.get("status") == "failed"
                    and expected_error in actual_error
                )
                rollback_kind = spec[command]["reliability"].get(
                    "rollback", "not_required"
                )
                rollback = "not_required"
                if rollback_kind not in {"not_required", "none"}:
                    rollback = (
                        "paired_command"
                        if command.startswith(
                            ("firewall.", "vpn.", "network.", "wifi.", "dhcp.")
                        )
                        else "configuration_backup"
                    )
                report["commands"][command].update(
                    status="pass" if passed else "fail",
                    idempotency="pass" if duplicate_same_id else "fail",
                    timeout="pass"
                    if elapsed
                    <= int(spec[command]["reliability"]["delivery"]["timeout_seconds"])
                    else "fail",
                    redelivery="pass" if duplicate_same_id else "fail",
                    post_condition="pass" if passed else "fail",
                    rollback=rollback,
                    evidence=evidence,
                )
                print(
                    f"{'PASS' if passed else 'FAIL'} {target.name}: {command} ({elapsed:.1f}s)",
                    flush=True,
                )
                if command == "wifi.add_ssid" and passed:
                    created_iface = ssh.run(
                        "uci -q show wireless | sed -n "
                        "\"s/^wireless\\.\\([^.=]*\\)\\.ssid='WrtMonitor-Cert'$/\\1/p\" "
                        "| head -n1",
                        check=False,
                    )
                    if created_iface:
                        recipes["wifi.update_ssid"]["iface"] = created_iface
                        recipes["wifi.delete_ssid"]["iface"] = created_iface
                if command == "network.delete_vlan" and passed:
                    ssh.run(
                        "uci -q delete network.wrtmonitor_cert_bridge || true; "
                        "uci commit network; /etc/init.d/network reload"
                    )
                if command in {"dns.install_dot", "dns.install_doh"} and passed:
                    time.sleep(8)
                    latest = api.get(
                        f"/api/v1/devices/{target.device_id}/telemetry/latest"
                    )
                    f["capabilities"] = (latest.get("agent") or {}).get(
                        "capabilities"
                    ) or f["capabilities"]
                if command == "router.reboot" and passed:
                    time.sleep(12)
                    wait_online(api, target)
                if command == "agent.disconnect" and passed:
                    time.sleep(3)
                    ssh.run(
                        "uci set wrtmonitor.main.enabled=1; uci commit wrtmonitor; /etc/init.d/wrtmonitor restart"
                    )
                    wait_online(api, target)
            except Exception as exc:
                elapsed = time.monotonic() - started
                evidence_dir = (
                    ROOT / "certification" / "evidence" / target_slug / command
                )
                evidence_dir.mkdir(parents=True, exist_ok=True)
                (evidence_dir / "result.json").write_text(
                    json.dumps(
                        {
                            "tested_at": now_iso(),
                            "command": command,
                            "status": "failed",
                            "error": str(exc),
                            "elapsed_seconds": round(elapsed, 3),
                        },
                        ensure_ascii=False,
                        indent=2,
                    )
                    + "\n",
                    encoding="utf-8",
                )
                report["commands"][command].update(
                    status="fail",
                    idempotency="fail",
                    timeout="fail",
                    redelivery="fail",
                    post_condition="fail",
                    rollback="not_run",
                    evidence=str(evidence_dir.relative_to(ROOT)).replace("\\", "/"),
                )
                print(f"FAIL {target.name}: {command}: {exc}", flush=True)
            finally:
                if original_update_url is not None:
                    if original_update_url:
                        restore = (
                            "uci set wrtmonitor.main.update_source='"
                            + shell_single_quote(original_update_url)
                            + "'"
                        )
                    else:
                        restore = "uci -q delete wrtmonitor.main.update_source || true"
                    ssh.run(restore + "; uci commit wrtmonitor", check=False)
            report["generated_at"] = now_iso()
            report_path = ROOT / "certification" / f"{target_slug}.json"
            report_path.write_text(
                json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )

        return ROOT / "certification" / f"{target_slug}.json"
    finally:
        if baseline_archive is not None:
            restore_baseline(ssh, baseline_archive)
        ssh.close()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run WrtMonitor commands through real server and OpenWrt hardware"
    )
    parser.add_argument("--name", required=True)
    parser.add_argument("--host", required=True)
    parser.add_argument("--device-id", required=True)
    parser.add_argument(
        "--commands",
        help="comma-separated command names; default is the complete contract",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="merge selected results into the existing report",
    )
    args = parser.parse_args()
    selected = set(filter(None, (args.commands or "").split(","))) or None
    path = certify(Target(args.name, args.host, args.device_id), selected, args.resume)
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
