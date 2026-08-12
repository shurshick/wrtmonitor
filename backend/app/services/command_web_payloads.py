from __future__ import annotations

from typing import Any

from fastapi import HTTPException

from .command_common import ALLOWED_COMMANDS
from .command_validation import validate_command_payload


def build_command_payload_from_web_form(
    command_type: str,
    *,
    ssid: str = "",
    enabled: str = "true",
    wifi_password: str = "",
    channel: str = "",
    country: str = "",
    interval_seconds: str = "",
    radio: str = "",
    iface: str = "",
    interface: str = "",
    hostname: str = "",
    service: str = "",
    mac: str = "",
    ip: str = "",
    diagnostics_checks: list[str] | None = None,
    protocol: str = "",
    ip_address: str = "",
    netmask: str = "",
    gateway: str = "",
    dns: str = "",
    username: str = "",
    password: str = "",
    mtu: str = "",
    start: str = "",
    limit: str = "",
    leasetime: str = "",
    servers: str = "",
    name: str = "",
    external_port: str = "",
    internal_ip: str = "",
    internal_port: str = "",
    blocked: str = "true",
    zonename: str = "",
    timezone: str = "",
    download_kbps: str = "",
    upload_kbps: str = "",
    htmode: str = "",
    txpower: str = "",
    network: str = "",
    encryption: str = "",
    hidden: str = "false",
    isolate: str = "false",
    ieee80211r: str = "false",
    ieee80211k: str = "false",
    bss_transition: str = "false",
    mobility_domain: str = "",
    weekdays: list[str] | None = None,
    stop: str = "",
    mesh_id: str = "",
    public_key: str = "",
    preshared_key: str = "",
    allowed_ips: str = "",
    endpoint: str = "",
    config_text: str = "",
    source: str = "",
    destination: str = "",
    url: str = "",
    sha256: str = "",
    archive_base64: str = "",
    content: str = "",
    pid: str = "",
    signal: str = "",
    uci_section: str = "",
    ports: str = "",
    bridge: str = "false",
    stp: str = "false",
    igmp_snooping: str = "true",
    dhcp_enabled: str = "false",
    dhcp_start: str = "",
    dhcp_limit: str = "",
    dhcp_leasetime: str = "",
    policy: str = "guest",
    vlan_id: str = "",
    track_ips: str = "",
    check_interval: str = "",
    failure_interval: str = "",
    recovery_interval: str = "",
) -> dict[str, Any]:
    if command_type not in ALLOWED_COMMANDS:
        raise ValueError("Unsupported command")
    payload: dict[str, Any] = {}
    if command_type == "wifi.set_ssid":
        payload = {"ssid": ssid, "iface": iface}
    elif command_type == "wifi.set_enabled":
        payload = {"enabled": enabled.lower() == "true", "radio": radio}
    elif command_type == "wifi.set_password":
        payload = {"password": wifi_password, "iface": iface}
    elif command_type == "wifi.set_channel":
        payload = {"channel": channel, "radio": radio}
    elif command_type == "wifi.set_country":
        payload = {"country": country, "radio": radio}
    elif command_type == "wifi.set_radio":
        payload = {
            "radio": radio,
            "enabled": enabled.lower() == "true",
            "channel": channel,
            "country": country,
            "htmode": htmode,
            "txpower": txpower,
        }
    elif command_type == "wifi.add_ssid":
        payload = {
            "radio": radio,
            "ssid": ssid,
            "network": network or "lan",
            "encryption": encryption or "sae-mixed",
            "key": wifi_password,
            "hidden": hidden.lower() == "true",
            "isolate": isolate.lower() == "true",
        }
    elif command_type == "wifi.update_ssid":
        payload = {
            "iface": iface,
            "ssid": ssid,
            "network": network or "lan",
            "encryption": encryption or "sae-mixed",
            "key": wifi_password,
            "enabled": enabled.lower() == "true",
            "hidden": hidden.lower() == "true",
            "isolate": isolate.lower() == "true",
            "ieee80211r": ieee80211r.lower() == "true",
            "ieee80211k": ieee80211k.lower() == "true",
            "bss_transition": bss_transition.lower() == "true",
            "mobility_domain": mobility_domain,
        }
    elif command_type == "wifi.delete_ssid":
        payload = {"iface": iface}
    elif command_type == "wifi.set_schedule":
        payload = {
            "radio": radio,
            "enabled": enabled.lower() == "true",
            "weekdays": weekdays or [],
            "start": start,
            "stop": stop,
        }
    elif command_type == "wifi.set_mesh":
        payload = {
            "radio": radio,
            "enabled": enabled.lower() == "true",
            "mesh_id": mesh_id,
            "network": network or "lan",
            "encryption": encryption or "sae",
            "key": wifi_password,
        }
    elif command_type == "network.interface_restart":
        payload = {"interface": interface}
    elif command_type == "network.set_wan":
        payload = {
            "interface": interface or "wan",
            "protocol": protocol,
            "ip_address": ip_address,
            "netmask": netmask,
            "gateway": gateway,
            "dns": dns,
            "username": username,
            "password": password,
            "mtu": mtu,
        }
    elif command_type == "network.set_lan":
        payload = {
            "interface": interface or "lan",
            "ip_address": ip_address,
            "netmask": netmask,
        }
    elif command_type == "network.set_ipv6":
        payload = {
            "interface": interface or "lan",
            "enabled": enabled.lower() == "true",
            "assignment_length": limit,
            "ra": protocol or "server",
            "dhcpv6": gateway or "server",
            "ndp": dns or "server",
        }
    elif command_type == "network.set_segment":
        payload = {
            "name": name,
            "protocol": protocol or "static",
            "device": interface,
            "bridge_section": uci_section,
            "ip_address": ip_address,
            "netmask": netmask,
            "enabled": enabled.lower() == "true",
            "bridge": bridge.lower() == "true",
            "ports": ports,
            "stp": stp.lower() == "true",
            "igmp_snooping": igmp_snooping.lower() == "true",
            "dhcp_enabled": dhcp_enabled.lower() == "true",
            "dhcp_start": dhcp_start,
            "dhcp_limit": dhcp_limit,
            "dhcp_leasetime": dhcp_leasetime,
            "policy": policy,
        }
    elif command_type == "network.delete_segment":
        payload = {"name": name}
    elif command_type == "network.set_vlan":
        payload = {
            "section": uci_section,
            "device": interface,
            "vlan_id": vlan_id,
            "ports": ports,
        }
    elif command_type == "network.delete_vlan":
        payload = {"section": uci_section}
    elif command_type == "network.set_multiwan":
        payload = {
            "enabled": enabled.lower() == "true",
            "primary_interface": interface or "wan",
            "secondary_interface": name,
            "primary_metric": external_port or "10",
            "secondary_metric": internal_port or "20",
            "track_ips": track_ips,
            "check_interval": check_interval or "5",
            "failure_interval": failure_interval or "3",
            "recovery_interval": recovery_interval or "3",
        }
    elif command_type == "network.set_route":
        payload = {
            "section": uci_section,
            "name": name,
            "interface": interface or "wan",
            "target": ip_address,
            "gateway": gateway,
            "metric": mtu or "0",
        }
    elif command_type == "network.delete_route":
        payload = {"section": uci_section, "name": name}
    elif command_type == "network.set_ddns":
        payload = {
            "name": name,
            "enabled": enabled.lower() == "true",
            "provider": protocol,
            "domain": hostname,
            "username": username,
            "password": password,
            "interface": interface or "wan",
        }
    elif command_type == "network.set_upnp":
        payload = {
            "enabled": enabled.lower() == "true",
            "secure_mode": blocked.lower() == "true",
        }
    elif command_type == "firewall.set_zone":
        payload = {
            "section": uci_section,
            "name": name,
            "networks": network,
            "input": protocol,
            "output": username,
            "forward": password,
            "masquerade": enabled.lower() == "true",
        }
    elif command_type == "firewall.delete_zone":
        payload = {"section": uci_section, "name": name}
    elif command_type == "firewall.set_forwarding":
        payload = {
            "section": uci_section,
            "src": interface or name,
            "dest": network,
            "enabled": enabled.lower() == "true",
        }
    elif command_type == "firewall.delete_forwarding":
        payload = {"section": uci_section, "src": interface or name, "dest": network}
    elif command_type == "firewall.set_rule":
        payload = {
            "section": uci_section,
            "name": name,
            "src": interface,
            "dest": network,
            "protocol": protocol,
            "src_ip": ip_address,
            "dest_ip": internal_ip,
            "src_port": external_port,
            "dest_port": internal_port,
            "target": hostname,
        }
    elif command_type == "firewall.delete_rule":
        payload = {"section": uci_section, "name": name}
    elif command_type == "vpn.wireguard.set_interface":
        payload = {
            "name": name or interface,
            "enabled": enabled.lower() == "true",
            "mode": protocol or "server",
            "addresses": ip_address,
            "listen_port": external_port or "51820",
            "private_key": password,
            "mtu": mtu or "1420",
        }
    elif command_type == "vpn.wireguard.set_peer":
        payload = {
            "interface": interface,
            "name": name,
            "public_key": public_key or username,
            "preshared_key": preshared_key or password,
            "allowed_ips": allowed_ips or ip_address,
            "endpoint": endpoint or hostname,
            "persistent_keepalive": internal_port or "0",
            "route_allowed_ips": enabled.lower() == "true",
        }
    elif command_type in {"vpn.wireguard.delete_peer", "vpn.wireguard.export_peer"}:
        payload = {"interface": interface, "name": name}
    elif command_type == "vpn.wireguard.delete_interface":
        payload = {"name": name or interface}
    elif command_type == "vpn.openvpn.set_client":
        payload = {
            "name": name,
            "enabled": enabled.lower() == "true",
            "config": config_text or protocol,
        }
    elif command_type in {"vpn.openvpn.delete_client", "vpn.openvpn.export_client"}:
        payload = {"name": name}
    elif command_type == "vpn.openvpn.set_enabled":
        payload = {"name": name, "enabled": enabled.lower() == "true"}
    elif command_type == "vpn.policy.set":
        payload = {
            "section": uci_section,
            "name": name,
            "enabled": enabled.lower() == "true",
            "interface": interface,
            "source": source or ip_address or mac,
            "destination": destination or network,
            "protocol": protocol or "all",
        }
    elif command_type == "vpn.policy.delete":
        payload = {"section": uci_section, "name": name}
    elif command_type in {
        "maintenance.package.install",
        "maintenance.package.remove",
        "maintenance.package.upgrade",
    }:
        payload = {"package": name}
    elif command_type == "maintenance.backup.restore":
        payload = {"archive_base64": archive_base64 or config_text}
    elif command_type == "maintenance.sysupgrade.check":
        payload = {
            "url": url or hostname,
            "sha256": sha256 or password,
            "expected_model": name,
            "preserve_config": enabled.lower() == "true",
        }
    elif command_type == "maintenance.sysupgrade.apply":
        payload = {
            "sha256": sha256 or password,
            "preserve_config": enabled.lower() == "true",
        }
    elif command_type == "maintenance.logs.read":
        payload = {"lines": limit or "100"}
    elif command_type == "maintenance.process.signal":
        payload = {"pid": pid or internal_port, "signal": signal or protocol or "TERM"}
    elif command_type == "maintenance.cron.set":
        payload = {"content": content or config_text}
    elif command_type == "maintenance.service.set":
        payload = {"service": service or name, "action": protocol}
    elif command_type == "maintenance.module.configure":
        payload = {"module": name, "action": protocol}
    elif command_type in {
        "maintenance.packages.refresh",
        "maintenance.processes.read",
        "maintenance.cron.read",
        "maintenance.services.read",
        "maintenance.backup.create",
        "maintenance.diagnostics.bundle",
        "maintenance.recovery.enable",
        "maintenance.recovery.disable",
    }:
        payload = {}
    elif command_type == "system.set_hostname":
        payload = {"hostname": hostname}
    elif command_type == "system.restart_service":
        payload = {"service": service}
    elif command_type == "dhcp.set_lease":
        payload = {"mac": mac, "ip": ip, "hostname": hostname}
    elif command_type == "dhcp.delete_lease":
        payload = {"mac": mac}
    elif command_type == "dhcp.set_pool":
        payload = {
            "interface": interface or "lan",
            "start": start,
            "limit": limit,
            "leasetime": leasetime,
        }
    elif command_type == "dns.set_servers":
        payload = {"servers": servers}
    elif command_type in {"dns.install_dot", "dns.install_doh"}:
        payload = {"mode": command_type.rsplit("_", 1)[1]}
    elif command_type in {"dns.set_dot", "dns.set_doh"}:
        payload = {
            "mode": command_type.rsplit("_", 1)[1],
            "provider": name or "cloudflare",
            "enabled": enabled.lower() == "true",
        }
    elif command_type == "firewall.set_port_forward":
        payload = {
            "section": uci_section,
            "name": name,
            "protocol": protocol,
            "external_port": external_port,
            "internal_ip": internal_ip,
            "internal_port": internal_port,
        }
    elif command_type == "firewall.delete_port_forward":
        payload = {"section": uci_section, "name": name}
    elif command_type == "firewall.set_redirect":
        payload = {
            "section": uci_section,
            "name": name,
            "enabled": enabled.lower() == "true",
            "src": interface or "wan",
            "dest": network or "lan",
            "protocol": protocol or "tcpudp",
            "src_ip": source,
            "src_port": external_port,
            "dest_ip": internal_ip or destination,
            "dest_port": internal_port,
            "target": hostname or "DNAT",
        }
    elif command_type == "firewall.delete_redirect":
        payload = {"section": uci_section, "name": name}
    elif command_type == "client.set_blocked":
        payload = {"mac": mac, "blocked": blocked.lower() == "true"}
    elif command_type == "qos.set_sqm":
        payload = {
            "enabled": enabled.lower() == "true",
            "interface": interface,
            "download_kbps": download_kbps,
            "upload_kbps": upload_kbps,
            "profile": name or "balanced",
            "qdisc": protocol or "cake",
            "script": source or "piece_of_cake.qos",
            "qdisc_options": config_text,
            "schedule": {
                "enabled": blocked.lower() == "true",
                "weekdays": weekdays or [],
                "start": start,
                "stop": stop,
            },
        }
    elif command_type == "wifi.set_guest":
        payload = {
            "enabled": enabled.lower() == "true",
            "ssid": ssid,
            "password": wifi_password,
            "radio": radio,
        }
    elif command_type == "system.set_timezone":
        payload = {"zonename": zonename, "timezone": timezone}
    elif command_type == "system.set_ntp":
        payload = {"enabled": enabled.lower() == "true", "servers": servers}
    elif command_type == "agent.set_auto_update":
        payload = {"enabled": enabled.lower() == "true"}
    elif command_type == "agent.set_interval":
        payload = {"interval_seconds": interval_seconds}
    elif command_type == "diagnostics.run":
        payload = {"checks": diagnostics_checks or []}
    try:
        return validate_command_payload(command_type, payload)
    except HTTPException as exc:
        raise ValueError(str(exc.detail)) from exc


__all__ = ["build_command_payload_from_web_form"]
