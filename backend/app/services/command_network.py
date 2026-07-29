from __future__ import annotations

from ipaddress import (
    AddressValueError,
    IPv4Address,
    ip_address,
    ip_network,
)
import re
from typing import Any

from fastapi import HTTPException

from .command_common import (
    _boolean,
    _integer,
    _ipv4,
    _name,
    _normalize_hostname_payload,
    _optional_string,
    _require_string,
    _safe_identifier,
    _string_list,
    _uci_section,
)


def _normalize_interface_payload(payload: dict[str, Any]) -> dict[str, Any]:
    interface = _require_string(payload, "interface", max_length=32)
    return {"interface": _safe_identifier(interface, "interface", r"[A-Za-z0-9_.-]+")}


def _normalize_mac(value: str) -> str:
    normalized = value.lower().replace("-", ":")
    return _safe_identifier(normalized, "mac", r"(?:[0-9a-f]{2}:){5}[0-9a-f]{2}")


def _normalize_dhcp_lease_payload(
    payload: dict[str, Any], *, delete: bool = False
) -> dict[str, Any]:
    mac = _normalize_mac(_require_string(payload, "mac", max_length=17))
    if delete:
        return {"mac": mac}
    ip = _require_string(payload, "ip", max_length=15)
    try:
        ip = str(IPv4Address(ip))
    except AddressValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid IPv4 address") from exc
    hostname = _normalize_hostname_payload(
        {"hostname": _require_string(payload, "hostname", max_length=63)}
    )["hostname"]
    return {"mac": mac, "ip": ip, "hostname": hostname}


def _normalize_wan_payload(payload: dict[str, Any]) -> dict[str, Any]:
    interface = _safe_identifier(
        str(payload.get("interface") or "wan"), "interface", r"[A-Za-z0-9_.-]+"
    )
    protocol = str(payload.get("protocol") or "dhcp").lower()
    if protocol not in {"dhcp", "static", "pppoe"}:
        raise HTTPException(
            status_code=400, detail="WAN protocol must be dhcp, static or pppoe"
        )
    result: dict[str, Any] = {"interface": interface, "protocol": protocol}
    mtu = _integer(payload, "mtu", 576, 9200, required=False)
    if mtu is not None:
        result["mtu"] = mtu
    dns = _string_list(payload, "dns")
    for server in dns:
        try:
            IPv4Address(server)
        except AddressValueError as exc:
            raise HTTPException(
                status_code=400, detail=f"Invalid DNS server: {server}"
            ) from exc
    if dns:
        result["dns"] = dns
    if protocol == "static":
        result.update(
            ip_address=_ipv4(payload, "ip_address"), netmask=_ipv4(payload, "netmask")
        )
        gateway = _ipv4(payload, "gateway", required=False)
        if gateway:
            result["gateway"] = gateway
    elif protocol == "pppoe":
        result["username"] = _require_string(payload, "username", max_length=128)
        result["password"] = _require_string(payload, "password", max_length=128)
    return result


def _normalize_lan_payload(payload: dict[str, Any]) -> dict[str, Any]:
    interface = _safe_identifier(
        str(payload.get("interface") or "lan"), "interface", r"[A-Za-z0-9_.-]+"
    )
    return {
        "interface": interface,
        "ip_address": _ipv4(payload, "ip_address"),
        "netmask": _ipv4(payload, "netmask"),
    }


def _normalize_dhcp_pool_payload(payload: dict[str, Any]) -> dict[str, Any]:
    interface = _safe_identifier(
        str(payload.get("interface") or "lan"), "interface", r"[A-Za-z0-9_.-]+"
    )
    leasetime = _require_string(payload, "leasetime", max_length=12).lower()
    _safe_identifier(leasetime, "leasetime", r"[1-9][0-9]*[mh]")
    return {
        "interface": interface,
        "start": _integer(payload, "start", 1, 254),
        "limit": _integer(payload, "limit", 1, 253),
        "leasetime": leasetime,
    }


def _normalize_dns_payload(payload: dict[str, Any]) -> dict[str, Any]:
    servers = _string_list(payload, "servers", required=True)
    for server in servers:
        try:
            IPv4Address(server)
        except AddressValueError as exc:
            raise HTTPException(
                status_code=400, detail=f"Invalid DNS server: {server}"
            ) from exc
    return {"servers": servers}


def _normalize_client_block_payload(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload.get("blocked"), bool):
        raise HTTPException(
            status_code=400, detail="Field 'blocked' must be provided as boolean"
        )
    return {
        "mac": _normalize_mac(_require_string(payload, "mac", max_length=17)),
        "blocked": payload["blocked"],
    }


def _normalize_client_policy_payload(payload: dict[str, Any]) -> dict[str, Any]:
    mac = _normalize_mac(_require_string(payload, "mac", max_length=17))
    if not isinstance(payload.get("blocked"), bool):
        raise HTTPException(status_code=400, detail="Field 'blocked' must be boolean")
    schedule = payload.get("schedule") or {}
    if not isinstance(schedule, dict):
        raise HTTPException(
            status_code=400, detail="Field 'schedule' must be an object"
        )
    weekdays = schedule.get("weekdays") or []
    allowed_days = {"mon", "tue", "wed", "thu", "fri", "sat", "sun"}
    if not isinstance(weekdays, list) or any(
        str(day).lower() not in allowed_days for day in weekdays
    ):
        raise HTTPException(status_code=400, detail="Invalid policy weekdays")
    result_schedule = {
        "enabled": bool(schedule.get("enabled", False)),
        "weekdays": [str(day).lower() for day in weekdays],
        "start": str(schedule.get("start") or ""),
        "stop": str(schedule.get("stop") or ""),
    }
    for field in ("start", "stop"):
        if result_schedule[field] and not re.fullmatch(
            r"(?:[01]\d|2[0-3]):[0-5]\d", result_schedule[field]
        ):
            raise HTTPException(status_code=400, detail=f"Invalid schedule {field}")
    qos = payload.get("qos") or {}
    if not isinstance(qos, dict):
        raise HTTPException(status_code=400, detail="Field 'qos' must be an object")
    priority = str(qos.get("priority") or "normal")
    if priority not in {"low", "normal", "high", "realtime"}:
        raise HTTPException(status_code=400, detail="Invalid QoS priority")
    return {
        "mac": mac,
        "blocked": payload["blocked"],
        "schedule": result_schedule,
        "qos": {
            "priority": priority,
            "download_kbps": _integer(
                {"download_kbps": qos.get("download_kbps", 0)},
                "download_kbps",
                0,
                10_000_000,
            ),
            "upload_kbps": _integer(
                {"upload_kbps": qos.get("upload_kbps", 0)}, "upload_kbps", 0, 10_000_000
            ),
        },
    }


def _normalize_sqm_payload(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload.get("enabled"), bool):
        raise HTTPException(status_code=400, detail="Field 'enabled' must be boolean")
    interface = _safe_identifier(
        _require_string(payload, "interface", max_length=40),
        "interface",
        r"[A-Za-z0-9_.@:-]+",
    )
    return {
        "enabled": payload["enabled"],
        "interface": interface,
        "download_kbps": _integer(payload, "download_kbps", 0, 10_000_000),
        "upload_kbps": _integer(payload, "upload_kbps", 0, 10_000_000),
        "qdisc": "cake",
        "script": "piece_of_cake.qos",
    }


def _normalize_ipv6_payload(payload: dict[str, Any]) -> dict[str, Any]:
    result = {
        "interface": _safe_identifier(
            str(payload.get("interface") or "lan"), "interface", r"[A-Za-z0-9_.-]+"
        ),
        "enabled": _boolean(payload, "enabled"),
    }
    if result["enabled"]:
        result["assignment_length"] = _integer(payload, "assignment_length", 48, 64)
        for field in ("ra", "dhcpv6", "ndp"):
            value = str(payload.get(field) or "server").lower()
            if value not in {"disabled", "server", "relay", "hybrid"}:
                raise HTTPException(
                    status_code=400, detail=f"Invalid IPv6 {field} mode"
                )
            result[field] = value
    return result


def _network_port(value: str, *, vlan: bool = False) -> str:
    pattern = r"[A-Za-z0-9_.@-]+(?::[ut](?:\*)?)?" if vlan else r"[A-Za-z0-9_.@-]+"
    return _safe_identifier(value, "ports", pattern)


def _normalize_segment_payload(payload: dict[str, Any]) -> dict[str, Any]:
    name = _safe_identifier(
        _require_string(payload, "name", max_length=32),
        "name",
        r"[A-Za-z0-9_][A-Za-z0-9_-]*",
    )
    protocol = str(payload.get("protocol") or "static").lower()
    if protocol not in {"static", "dhcp", "none"}:
        raise HTTPException(status_code=400, detail="Invalid segment protocol")
    ports = [_network_port(value) for value in _string_list(payload, "ports")]
    if len(ports) > 16:
        raise HTTPException(
            status_code=400, detail="A segment supports at most 16 ports"
        )
    bridge = _boolean(payload, "bridge", default=bool(ports))
    device = _optional_string(payload, "device") or (f"br-{name}" if bridge else "")
    if device:
        device = _safe_identifier(device, "device", r"[A-Za-z0-9_.@:-]+")
    result: dict[str, Any] = {
        "name": name,
        "protocol": protocol,
        "device": device,
        "bridge_section": _uci_section({"section": payload.get("bridge_section")}),
        "enabled": _boolean(payload, "enabled", default=True),
        "bridge": bridge,
        "ports": ports,
        "stp": _boolean(payload, "stp", default=False),
        "igmp_snooping": _boolean(payload, "igmp_snooping", default=True),
        "dhcp_enabled": _boolean(payload, "dhcp_enabled", default=False),
        "policy": str(payload.get("policy") or "guest").lower(),
    }
    if result["policy"] not in {"trusted", "guest", "isolated"}:
        raise HTTPException(status_code=400, detail="Invalid segment policy")
    if protocol == "static":
        result["ip_address"] = _ipv4(payload, "ip_address")
        result["netmask"] = _ipv4(payload, "netmask")
    if result["dhcp_enabled"]:
        if protocol != "static":
            raise HTTPException(
                status_code=400, detail="DHCP server requires a static segment address"
            )
        result["dhcp_start"] = _integer(payload, "dhcp_start", 1, 254)
        result["dhcp_limit"] = _integer(payload, "dhcp_limit", 1, 253)
        leasetime = _require_string(payload, "dhcp_leasetime", max_length=12).lower()
        result["dhcp_leasetime"] = _safe_identifier(
            leasetime, "dhcp_leasetime", r"[1-9][0-9]*[mh]"
        )
    return result


def _normalize_vlan_payload(
    payload: dict[str, Any], *, delete: bool = False
) -> dict[str, Any]:
    section = _uci_section(payload)
    if delete:
        if not section:
            raise HTTPException(status_code=400, detail="VLAN section is required")
        return {"section": section}
    ports = [
        _network_port(value, vlan=True)
        for value in _string_list(payload, "ports", required=True)
    ]
    if len(ports) > 16:
        raise HTTPException(status_code=400, detail="A VLAN supports at most 16 ports")
    return {
        "section": section,
        "device": _safe_identifier(
            _require_string(payload, "device", max_length=32),
            "device",
            r"[A-Za-z0-9_.@:-]+",
        ),
        "vlan_id": _integer(payload, "vlan_id", 1, 4094),
        "ports": ports,
    }


def _normalize_multiwan_payload(payload: dict[str, Any]) -> dict[str, Any]:
    track_ips = _string_list(payload, "track_ips") or ["1.1.1.1", "8.8.8.8"]
    for address in track_ips:
        try:
            IPv4Address(address)
        except AddressValueError as exc:
            raise HTTPException(
                status_code=400, detail=f"Invalid Multi-WAN tracking address: {address}"
            ) from exc
    return {
        "enabled": _boolean(payload, "enabled"),
        "primary_interface": _safe_identifier(
            str(payload.get("primary_interface") or "wan"),
            "primary_interface",
            r"[A-Za-z0-9_.-]+",
        ),
        "secondary_interface": _safe_identifier(
            _require_string(payload, "secondary_interface", max_length=32),
            "secondary_interface",
            r"[A-Za-z0-9_.-]+",
        ),
        "primary_metric": _integer(payload, "primary_metric", 1, 255),
        "secondary_metric": _integer(payload, "secondary_metric", 1, 255),
        "track_ips": track_ips,
        "check_interval": _integer(payload, "check_interval", 1, 600, required=False)
        or 5,
        "failure_interval": _integer(payload, "failure_interval", 1, 20, required=False)
        or 3,
        "recovery_interval": _integer(
            payload, "recovery_interval", 1, 20, required=False
        )
        or 3,
    }


def _normalize_route_payload(payload: dict[str, Any]) -> dict[str, Any]:
    target = _require_string(payload, "target", max_length=64)
    try:
        target = str(ip_network(target, strict=False))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid route target") from exc
    gateway = _optional_string(payload, "gateway")
    if gateway:
        try:
            gateway = str(ip_address(gateway))
        except ValueError as exc:
            raise HTTPException(
                status_code=400, detail="Invalid route gateway"
            ) from exc
    return {
        "section": _uci_section(payload),
        "name": _name(payload),
        "interface": _safe_identifier(
            str(payload.get("interface") or "wan"), "interface", r"[A-Za-z0-9_.-]+"
        ),
        "target": target,
        "gateway": gateway or "",
        "metric": _integer(payload, "metric", 0, 65535, required=False) or 0,
    }


def _normalize_ddns_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": _name(payload),
        "enabled": _boolean(payload, "enabled"),
        "provider": _safe_identifier(
            _require_string(payload, "provider", max_length=64),
            "provider",
            r"[A-Za-z0-9_.-]+",
        ),
        "domain": _require_string(payload, "domain", max_length=253),
        "username": _optional_string(payload, "username") or "",
        "password": _optional_string(payload, "password") or "",
        "interface": _safe_identifier(
            str(payload.get("interface") or "wan"), "interface", r"[A-Za-z0-9_.-]+"
        ),
    }


__all__ = [
    "_normalize_interface_payload",
    "_normalize_mac",
    "_normalize_dhcp_lease_payload",
    "_normalize_wan_payload",
    "_normalize_lan_payload",
    "_normalize_dhcp_pool_payload",
    "_normalize_dns_payload",
    "_normalize_client_block_payload",
    "_normalize_client_policy_payload",
    "_normalize_sqm_payload",
    "_normalize_ipv6_payload",
    "_network_port",
    "_normalize_segment_payload",
    "_normalize_vlan_payload",
    "_normalize_multiwan_payload",
    "_normalize_route_payload",
    "_normalize_ddns_payload",
]
