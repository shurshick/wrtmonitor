from __future__ import annotations

from ipaddress import (
    ip_interface,
    ip_network,
)
import re
from typing import Any

from fastapi import HTTPException

from .command_common import (
    _boolean,
    _integer,
    _name,
    _optional_string,
    _require_string,
    _safe_identifier,
    _string_list,
    _uci_section,
)


def _wireguard_key(payload: dict[str, Any], field: str, *, required: bool) -> str:
    value = _optional_string(payload, field) or ""
    if not value and not required:
        return ""
    if not re.fullmatch(r"[A-Za-z0-9+/]{42}[AEIMQUYcgkosw048]=", value):
        raise HTTPException(status_code=400, detail=f"Invalid WireGuard {field}")
    return value


def _normalize_wireguard_interface_payload(payload: dict[str, Any]) -> dict[str, Any]:
    addresses = _string_list(payload, "addresses", required=True)
    try:
        addresses = [str(ip_interface(value)) for value in addresses]
    except ValueError as exc:
        raise HTTPException(
            status_code=400, detail="Invalid WireGuard address"
        ) from exc
    return {
        "name": _name(payload),
        "enabled": _boolean(payload, "enabled"),
        "mode": _safe_identifier(
            str(payload.get("mode") or "server"), "mode", r"(?:server|client)"
        ),
        "addresses": addresses,
        "listen_port": _integer(payload, "listen_port", 1, 65535),
        "private_key": _wireguard_key(payload, "private_key", required=False),
        "mtu": _integer(payload, "mtu", 1280, 9200, required=False) or 1420,
    }


def _normalize_wireguard_peer_payload(payload: dict[str, Any]) -> dict[str, Any]:
    allowed_ips = _string_list(payload, "allowed_ips", required=True)
    try:
        allowed_ips = [str(ip_network(value, strict=False)) for value in allowed_ips]
    except ValueError as exc:
        raise HTTPException(
            status_code=400, detail="Invalid WireGuard allowed IP"
        ) from exc
    endpoint = _optional_string(payload, "endpoint") or ""
    if endpoint and not re.fullmatch(
        r"(?:\[[0-9A-Fa-f:]+\]|[A-Za-z0-9_.-]+):[0-9]{1,5}", endpoint
    ):
        raise HTTPException(status_code=400, detail="Invalid WireGuard endpoint")
    if endpoint and int(endpoint.rsplit(":", 1)[1]) > 65535:
        raise HTTPException(status_code=400, detail="Invalid WireGuard endpoint port")
    return {
        "interface": _safe_identifier(
            _require_string(payload, "interface", max_length=32),
            "interface",
            r"[A-Za-z0-9_.-]+",
        ),
        "name": _name(payload),
        "public_key": _wireguard_key(payload, "public_key", required=True),
        "preshared_key": _wireguard_key(payload, "preshared_key", required=False),
        "allowed_ips": allowed_ips,
        "endpoint": endpoint,
        "persistent_keepalive": _integer(
            payload, "persistent_keepalive", 0, 65535, required=False
        )
        or 0,
        "route_allowed_ips": _boolean(payload, "route_allowed_ips", default=True),
    }


def _normalize_openvpn_payload(payload: dict[str, Any]) -> dict[str, Any]:
    config = str(payload.get("config") or "").strip()
    if not config or len(config) > 65535:
        raise HTTPException(status_code=400, detail="Invalid OpenVPN config size")
    if any(ord(char) < 32 and char not in "\r\n\t" for char in config):
        raise HTTPException(
            status_code=400, detail="OpenVPN config contains invalid characters"
        )
    lowered_lines = [line.strip().lower() for line in config.splitlines()]
    forbidden = (
        "up ",
        "down ",
        "plugin ",
        "management ",
        "client-connect ",
        "client-disconnect ",
        "learn-address ",
        "route-up ",
    )
    if any(line.startswith(forbidden) for line in lowered_lines):
        raise HTTPException(
            status_code=400, detail="OpenVPN config contains unsafe directives"
        )
    if not any(line == "client" for line in lowered_lines):
        raise HTTPException(
            status_code=400, detail="OpenVPN client directive is required"
        )
    if not any(line.startswith("remote ") for line in lowered_lines):
        raise HTTPException(
            status_code=400, detail="OpenVPN remote directive is required"
        )
    return {
        "name": _name(payload),
        "enabled": _boolean(payload, "enabled"),
        "config": config,
    }


def _normalize_vpn_policy_payload(payload: dict[str, Any]) -> dict[str, Any]:
    source = _optional_string(payload, "source") or ""
    destination = _optional_string(payload, "destination") or ""
    if not source and not destination:
        raise HTTPException(
            status_code=400, detail="VPN policy requires source or destination"
        )
    for field, value in (("source", source), ("destination", destination)):
        if value and not re.fullmatch(r"[A-Za-z0-9_.:/,-]+", value):
            raise HTTPException(status_code=400, detail=f"Invalid VPN policy {field}")
    return {
        "section": _uci_section(payload),
        "name": _name(payload),
        "enabled": _boolean(payload, "enabled"),
        "interface": _safe_identifier(
            _require_string(payload, "interface", max_length=32),
            "interface",
            r"[A-Za-z0-9_.-]+",
        ),
        "source": source,
        "destination": destination,
        "protocol": _safe_identifier(
            str(payload.get("protocol") or "all"),
            "protocol",
            r"(?:all|tcp|udp|icmp)",
        ),
    }


__all__ = [
    "_wireguard_key",
    "_normalize_wireguard_interface_payload",
    "_normalize_wireguard_peer_payload",
    "_normalize_openvpn_payload",
    "_normalize_vpn_policy_payload",
]
