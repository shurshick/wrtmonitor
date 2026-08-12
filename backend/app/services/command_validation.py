from __future__ import annotations

from typing import Any
from fastapi import HTTPException

from .command_common import (
    _boolean,
    _integer,
    _name,
    _normalize_hostname_payload,
    _require_string,
    _safe_identifier,
    _uci_section,
)
from .command_wifi import (
    _normalize_guest_payload,
    _normalize_wifi_add_ssid_payload,
    _normalize_wifi_channel_payload,
    _normalize_wifi_country_payload,
    _normalize_wifi_enabled_payload,
    _normalize_wifi_mesh_payload,
    _normalize_wifi_password_payload,
    _normalize_wifi_radio_payload,
    _normalize_wifi_schedule_payload,
    _normalize_wifi_ssid_payload,
    _normalize_wifi_update_ssid_payload,
    _wifi_selector,
)
from .command_network import (
    _normalize_client_block_payload,
    _normalize_client_policy_payload,
    _normalize_ddns_payload,
    _normalize_dhcp_lease_payload,
    _normalize_dhcp_pool_payload,
    _normalize_dns_payload,
    _normalize_interface_payload,
    _normalize_ipv6_payload,
    _normalize_lan_payload,
    _normalize_multiwan_payload,
    _normalize_route_payload,
    _normalize_segment_payload,
    _normalize_sqm_payload,
    _normalize_vlan_payload,
    _normalize_wan_payload,
)
from .command_firewall import (
    _normalize_firewall_rule_payload,
    _normalize_forwarding_payload,
    _normalize_port_forward_payload,
    _normalize_redirect_payload,
    _normalize_zone_payload,
)
from .command_vpn import (
    _normalize_openvpn_payload,
    _normalize_vpn_policy_payload,
    _normalize_wireguard_interface_payload,
    _normalize_wireguard_peer_payload,
)
from .command_system import (
    _maintenance_backup_restore,
    _maintenance_cron,
    _maintenance_package,
    _maintenance_module,
    _maintenance_sysupgrade,
    _normalize_auto_update_payload,
    _normalize_diagnostics_payload,
    _normalize_interval_payload,
    _normalize_ntp_payload,
    _normalize_service_payload,
    _normalize_timezone_payload,
)


def validate_command_payload(
    command_type: str, payload: dict[str, Any]
) -> dict[str, Any]:
    normalized_payload = dict(payload or {})
    if command_type == "wifi.set_enabled":
        return _normalize_wifi_enabled_payload(normalized_payload)
    if command_type == "wifi.get_qr":
        return {"iface": _wifi_selector(normalized_payload, "iface")}
    if command_type == "wifi.set_ssid":
        return _normalize_wifi_ssid_payload(normalized_payload)
    if command_type == "wifi.set_password":
        return _normalize_wifi_password_payload(normalized_payload)
    if command_type == "wifi.set_channel":
        return _normalize_wifi_channel_payload(normalized_payload)
    if command_type == "wifi.set_country":
        return _normalize_wifi_country_payload(normalized_payload)
    if command_type == "wifi.set_radio":
        return _normalize_wifi_radio_payload(normalized_payload)
    if command_type == "wifi.add_ssid":
        return _normalize_wifi_add_ssid_payload(normalized_payload)
    if command_type == "wifi.update_ssid":
        return _normalize_wifi_update_ssid_payload(normalized_payload)
    if command_type == "wifi.delete_ssid":
        return {"iface": _wifi_selector(normalized_payload, "iface")}
    if command_type == "wifi.set_schedule":
        return _normalize_wifi_schedule_payload(normalized_payload)
    if command_type == "wifi.set_mesh":
        return _normalize_wifi_mesh_payload(normalized_payload)
    if command_type == "network.interface_restart":
        return _normalize_interface_payload(normalized_payload)
    if command_type == "network.set_wan":
        return _normalize_wan_payload(normalized_payload)
    if command_type == "network.set_lan":
        return _normalize_lan_payload(normalized_payload)
    if command_type == "network.set_ipv6":
        return _normalize_ipv6_payload(normalized_payload)
    if command_type == "network.set_segment":
        return _normalize_segment_payload(normalized_payload)
    if command_type == "network.delete_segment":
        name = _name(normalized_payload)
        if name in {"lan", "wan", "wan6", "loopback"}:
            raise HTTPException(
                status_code=400, detail="Core network segment cannot be deleted"
            )
        return {"name": name}
    if command_type == "network.set_vlan":
        return _normalize_vlan_payload(normalized_payload)
    if command_type == "network.delete_vlan":
        return _normalize_vlan_payload(normalized_payload, delete=True)
    if command_type == "network.set_multiwan":
        return _normalize_multiwan_payload(normalized_payload)
    if command_type == "network.set_route":
        return _normalize_route_payload(normalized_payload)
    if command_type == "network.delete_route":
        return {
            "section": _uci_section(normalized_payload),
            "name": _name(normalized_payload),
        }
    if command_type == "network.set_ddns":
        return _normalize_ddns_payload(normalized_payload)
    if command_type == "network.set_upnp":
        return {
            "enabled": _boolean(normalized_payload, "enabled"),
            "secure_mode": _boolean(normalized_payload, "secure_mode", default=True),
        }
    if command_type == "vpn.wireguard.set_interface":
        return _normalize_wireguard_interface_payload(normalized_payload)
    if command_type == "vpn.wireguard.set_peer":
        return _normalize_wireguard_peer_payload(normalized_payload)
    if command_type == "vpn.wireguard.delete_interface":
        return {"name": _name(normalized_payload)}
    if command_type in {"vpn.wireguard.delete_peer", "vpn.wireguard.export_peer"}:
        return {
            "interface": _safe_identifier(
                _require_string(normalized_payload, "interface", max_length=32),
                "interface",
                r"[A-Za-z0-9_.-]+",
            ),
            "name": _name(normalized_payload),
        }
    if command_type == "vpn.openvpn.set_client":
        return _normalize_openvpn_payload(normalized_payload)
    if command_type == "vpn.openvpn.delete_client":
        return {"name": _name(normalized_payload)}
    if command_type == "vpn.openvpn.set_enabled":
        return {
            "name": _name(normalized_payload),
            "enabled": _boolean(normalized_payload, "enabled"),
        }
    if command_type == "vpn.openvpn.export_client":
        return {"name": _name(normalized_payload)}
    if command_type == "vpn.policy.set":
        return _normalize_vpn_policy_payload(normalized_payload)
    if command_type == "vpn.policy.delete":
        return {
            "section": _uci_section(normalized_payload),
            "name": _name(normalized_payload),
        }
    if command_type in {
        "maintenance.packages.refresh",
        "maintenance.processes.read",
        "maintenance.cron.read",
        "maintenance.services.read",
        "maintenance.backup.create",
        "maintenance.diagnostics.bundle",
        "maintenance.recovery.enable",
        "maintenance.recovery.disable",
    }:
        return {}
    if command_type in {"maintenance.package.install", "maintenance.package.upgrade"}:
        return _maintenance_package(normalized_payload)
    if command_type == "maintenance.package.remove":
        return _maintenance_package(normalized_payload, remove=True)
    if command_type == "maintenance.module.configure":
        return _maintenance_module(normalized_payload)
    if command_type == "maintenance.backup.restore":
        return _maintenance_backup_restore(normalized_payload)
    if command_type == "maintenance.sysupgrade.check":
        return _maintenance_sysupgrade(normalized_payload, apply=False)
    if command_type == "maintenance.sysupgrade.apply":
        return _maintenance_sysupgrade(normalized_payload, apply=True)
    if command_type == "maintenance.logs.read":
        return {"lines": _integer(normalized_payload, "lines", 20, 500) or 100}
    if command_type == "maintenance.process.signal":
        return {
            "pid": _integer(normalized_payload, "pid", 2, 4_194_304),
            "signal": _safe_identifier(
                str(normalized_payload.get("signal") or "TERM"),
                "signal",
                r"(?:TERM|HUP|KILL)",
            ),
        }
    if command_type == "maintenance.cron.set":
        return _maintenance_cron(normalized_payload)
    if command_type == "maintenance.service.set":
        return {
            "service": _safe_identifier(
                str(normalized_payload.get("service") or ""),
                "service",
                r"[A-Za-z0-9_.-]{1,64}",
            ),
            "action": _safe_identifier(
                str(normalized_payload.get("action") or ""),
                "action",
                r"(?:start|stop|restart|enable|disable)",
            ),
        }
    if command_type == "firewall.set_zone":
        return _normalize_zone_payload(normalized_payload)
    if command_type == "firewall.delete_zone":
        zone = {
            "section": _uci_section(normalized_payload),
            "name": _name(normalized_payload),
        }
        if zone["name"] in {"lan", "wan"}:
            raise HTTPException(
                status_code=400, detail="core firewall zone cannot be deleted"
            )
        return zone
    if command_type == "firewall.set_forwarding":
        return _normalize_forwarding_payload(normalized_payload)
    if command_type == "firewall.delete_forwarding":
        return {
            "section": _uci_section(normalized_payload),
            "src": _name(normalized_payload, "src"),
            "dest": _name(normalized_payload, "dest"),
        }
    if command_type == "firewall.set_rule":
        return _normalize_firewall_rule_payload(normalized_payload)
    if command_type == "firewall.delete_rule":
        return {
            "section": _uci_section(normalized_payload),
            "name": _name(normalized_payload),
        }
    if command_type == "firewall.set_redirect":
        return _normalize_redirect_payload(normalized_payload)
    if command_type == "firewall.delete_redirect":
        return _normalize_redirect_payload(normalized_payload, delete=True)
    if command_type == "system.set_hostname":
        return _normalize_hostname_payload(normalized_payload)
    if command_type == "system.restart_service":
        return _normalize_service_payload(normalized_payload)
    if command_type == "dhcp.set_lease":
        return _normalize_dhcp_lease_payload(normalized_payload)
    if command_type == "dhcp.delete_lease":
        return _normalize_dhcp_lease_payload(normalized_payload, delete=True)
    if command_type == "dhcp.set_pool":
        return _normalize_dhcp_pool_payload(normalized_payload)
    if command_type == "dns.set_servers":
        return _normalize_dns_payload(normalized_payload)
    if command_type in {"dns.install_dot", "dns.install_doh"}:
        return {"mode": command_type.rsplit("_", 1)[1]}
    if command_type in {"dns.set_dot", "dns.set_doh"}:
        provider = str(normalized_payload.get("provider") or "cloudflare").strip()
        if provider not in {"cloudflare", "quad9", "google"}:
            raise HTTPException(status_code=400, detail="Unsupported DNS provider")
        return {
            "mode": command_type.rsplit("_", 1)[1],
            "provider": provider,
            "enabled": _boolean(normalized_payload, "enabled", default=True),
        }
    if command_type == "firewall.set_port_forward":
        return _normalize_port_forward_payload(normalized_payload)
    if command_type == "firewall.delete_port_forward":
        return _normalize_port_forward_payload(normalized_payload, delete=True)
    if command_type == "client.set_blocked":
        return _normalize_client_block_payload(normalized_payload)
    if command_type == "client.set_policy":
        return _normalize_client_policy_payload(normalized_payload)
    if command_type == "qos.set_sqm":
        return _normalize_sqm_payload(normalized_payload)
    if command_type == "wifi.set_guest":
        return _normalize_guest_payload(normalized_payload)
    if command_type == "system.set_timezone":
        return _normalize_timezone_payload(normalized_payload)
    if command_type == "system.set_ntp":
        return _normalize_ntp_payload(normalized_payload)
    if command_type == "diagnostics.run":
        return _normalize_diagnostics_payload(normalized_payload)
    if command_type == "agent.set_auto_update":
        return _normalize_auto_update_payload(normalized_payload)
    if command_type == "agent.set_interval":
        return _normalize_interval_payload(normalized_payload)
    return normalized_payload


__all__ = ["validate_command_payload"]
