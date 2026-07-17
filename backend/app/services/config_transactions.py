from __future__ import annotations

from ipaddress import IPv4Address, IPv4Network, ip_address, ip_network
from typing import Any
from uuid import UUID

from fastapi import HTTPException

from .telemetry import (
    normalize_clients_summary,
    normalize_network_summary,
    normalize_wifi_summary,
)


ROLLBACK_TIMEOUT_SECONDS = 90

CONFIG_TRANSACTION_SCOPES: dict[str, tuple[str, ...]] = {
    "wifi.set_enabled": ("wireless",),
    "wifi.set_ssid": ("wireless",),
    "wifi.set_password": ("wireless",),
    "wifi.set_channel": ("wireless",),
    "wifi.set_country": ("wireless",),
    "wifi.set_radio": ("wireless",),
    "wifi.add_ssid": ("wireless",),
    "wifi.update_ssid": ("wireless",),
    "wifi.delete_ssid": ("wireless",),
    "wifi.set_schedule": ("wireless", "wrtmonitor"),
    "wifi.set_mesh": ("wireless",),
    "wifi.set_guest": ("wireless", "network", "dhcp", "firewall"),
    "network.set_wan": ("network",),
    "network.set_lan": ("network",),
    "network.set_ipv6": ("network", "dhcp"),
    "network.set_multiwan": ("network", "mwan3"),
    "network.set_route": ("network",),
    "network.delete_route": ("network",),
    "network.set_ddns": ("ddns",),
    "network.set_upnp": ("upnpd", "firewall"),
    "dhcp.set_lease": ("dhcp",),
    "dhcp.delete_lease": ("dhcp",),
    "dhcp.set_pool": ("dhcp",),
    "dns.set_servers": ("dhcp",),
    "firewall.set_port_forward": ("firewall",),
    "firewall.delete_port_forward": ("firewall",),
    "firewall.set_zone": ("firewall",),
    "firewall.set_forwarding": ("firewall",),
    "firewall.set_rule": ("firewall",),
    "firewall.delete_rule": ("firewall",),
    "client.set_blocked": ("firewall",),
    "client.set_policy": ("firewall",),
    "qos.set_sqm": ("sqm",),
    "system.set_hostname": ("system",),
    "system.set_timezone": ("system",),
    "system.set_ntp": ("system",),
}

CONNECTIVITY_SENSITIVE_COMMANDS = {
    command_type
    for command_type in CONFIG_TRANSACTION_SCOPES
    if not command_type.startswith("system.")
}

SECRET_FIELDS = {"password", "key", "wifi_password"}
SELECTOR_FIELDS = {"iface", "radio", "interface"}


def is_transactional_command(command_type: str) -> bool:
    return command_type in CONFIG_TRANSACTION_SCOPES


def transaction_metadata(command_type: str, command_id: UUID) -> dict[str, Any]:
    return {
        "id": str(command_id),
        "schema_version": 1,
        "configs": list(CONFIG_TRANSACTION_SCOPES[command_type]),
        "rollback_timeout_seconds": ROLLBACK_TIMEOUT_SECONDS,
        "connectivity_sensitive": command_type in CONNECTIVITY_SENSITIVE_COMMANDS,
    }


def attach_transaction_metadata(
    command_type: str, payload: dict[str, Any], command_id: UUID
) -> dict[str, Any]:
    result = dict(payload)
    if is_transactional_command(command_type):
        result["_transaction"] = transaction_metadata(command_type, command_id)
    return result


def _interface(payload: dict[str, Any], name: str) -> dict[str, Any]:
    interfaces = normalize_network_summary(payload).get("interfaces") or []
    return next((item for item in interfaces if item.get("interface") == name), {})


def _lan_network(payload: dict[str, Any]) -> IPv4Network | None:
    lan = _interface(payload, "lan")
    addresses = lan.get("ipv4") or []
    if not addresses:
        return None
    prefix = 24
    raw_network = payload.get("network") or {}
    raw_interfaces = raw_network.get("interfaces") or raw_network.get("interface") or []
    raw_lan = next(
        (item for item in raw_interfaces if item.get("interface") == "lan"), {}
    )
    raw_addresses = raw_lan.get("ipv4-address") or []
    if raw_addresses and isinstance(raw_addresses[0], dict):
        prefix = int(raw_addresses[0].get("mask") or 24)
    try:
        return ip_network(f"{addresses[0]}/{prefix}", strict=False)
    except ValueError:
        return None


def _current_wifi_value(
    command_type: str, key: str, proposed: dict[str, Any], telemetry: dict[str, Any]
) -> Any:
    radios = normalize_wifi_summary(telemetry).get("radios") or []
    selected_radio = next(
        (radio for radio in radios if radio.get("id") == proposed.get("radio")),
        radios[0] if len(radios) == 1 else {},
    )
    interfaces = [
        iface for radio in radios for iface in (radio.get("interfaces") or [])
    ]
    selected_iface = next(
        (iface for iface in interfaces if iface.get("id") == proposed.get("iface")),
        interfaces[0] if len(interfaces) == 1 else {},
    )
    if command_type == "wifi.set_enabled" and key == "enabled":
        return bool(selected_radio.get("up")) if selected_radio else None
    if command_type == "wifi.set_ssid" and key == "ssid":
        return selected_iface.get("ssid")
    if command_type == "wifi.set_channel" and key == "channel":
        return selected_radio.get("channel")
    if command_type == "wifi.set_country" and key == "country":
        return selected_radio.get("country")
    return None


def _current_value(
    command_type: str, key: str, proposed: dict[str, Any], telemetry: dict[str, Any]
) -> Any:
    if command_type.startswith("wifi."):
        return _current_wifi_value(command_type, key, proposed, telemetry)
    if command_type in {"network.set_wan", "network.set_lan"}:
        interface = _interface(telemetry, str(proposed.get("interface") or "wan"))
        return {
            "protocol": interface.get("proto"),
            "ip_address": (interface.get("ipv4") or [None])[0],
            "gateway": interface.get("gateway"),
            "dns": interface.get("dns"),
        }.get(key)
    if command_type == "system.set_hostname" and key == "hostname":
        return (telemetry.get("system") or {}).get("hostname")
    if command_type in {"dhcp.set_lease", "dhcp.delete_lease"}:
        mac = str(proposed.get("mac") or "").lower()
        clients = normalize_clients_summary(telemetry).get("items") or []
        client = next((item for item in clients if item.get("mac") == mac), {})
        return client.get(key)
    return None


def _display_value(key: str, value: Any) -> Any:
    if key in SECRET_FIELDS and value not in (None, ""):
        return "********"
    return value


def preflight_errors(
    command_type: str, payload: dict[str, Any], telemetry: dict[str, Any] | None = None
) -> list[str]:
    errors: list[str] = []
    telemetry = telemetry or {}
    try:
        if command_type == "network.set_wan" and payload.get("protocol") == "static":
            network = ip_network(
                f"{payload['ip_address']}/{payload['netmask']}", strict=False
            )
            gateway = ip_address(str(payload.get("gateway") or payload["ip_address"]))
            if gateway not in network:
                errors.append("WAN gateway must belong to the configured subnet")
        elif command_type == "network.set_lan":
            network = ip_network(
                f"{payload['ip_address']}/{payload['netmask']}", strict=False
            )
            address = ip_address(str(payload["ip_address"]))
            if address in {network.network_address, network.broadcast_address}:
                errors.append("LAN address cannot be a network or broadcast address")
        elif command_type == "dhcp.set_pool":
            if int(payload["start"]) + int(payload["limit"]) > 255:
                errors.append("DHCP pool exceeds the IPv4 /24 host range")
        elif command_type in {"dhcp.set_lease", "firewall.set_port_forward"}:
            address_key = "ip" if command_type == "dhcp.set_lease" else "internal_ip"
            address = IPv4Address(str(payload[address_key]))
            lan_network = _lan_network(telemetry)
            if lan_network and address not in lan_network:
                errors.append(f"{address_key} must belong to the current LAN subnet")
    except (KeyError, TypeError, ValueError):
        errors.append("Configuration cannot be represented as a valid network")
    return errors


def ensure_preflight_valid(
    command_type: str, payload: dict[str, Any], telemetry: dict[str, Any] | None = None
) -> None:
    errors = preflight_errors(command_type, payload, telemetry)
    if errors:
        raise HTTPException(status_code=409, detail={"preflight_errors": errors})


def build_command_preview(
    command_type: str, payload: dict[str, Any], telemetry: dict[str, Any] | None = None
) -> dict[str, Any]:
    telemetry = telemetry or {}
    errors = preflight_errors(command_type, payload, telemetry)
    transactional = is_transactional_command(command_type)
    changes = []
    for key, proposed in payload.items():
        if key.startswith("_") or key in SELECTOR_FIELDS:
            continue
        current = _current_value(command_type, key, payload, telemetry)
        if current == proposed and key not in SECRET_FIELDS:
            continue
        changes.append(
            {
                "field": key,
                "current": _display_value(key, current),
                "proposed": _display_value(key, proposed),
            }
        )
    warnings: list[str] = []
    if transactional:
        warnings.append("A UCI backup will be created before applying changes")
    if command_type in CONNECTIVITY_SENSITIVE_COMMANDS:
        warnings.append(
            f"Connectivity must recover within {ROLLBACK_TIMEOUT_SECONDS} seconds or the agent will roll back"
        )
    return {
        "command_type": command_type,
        "transactional": transactional,
        "configs": list(CONFIG_TRANSACTION_SCOPES.get(command_type, ())),
        "rollback_timeout_seconds": ROLLBACK_TIMEOUT_SECONDS if transactional else None,
        "connectivity_sensitive": command_type in CONNECTIVITY_SENSITIVE_COMMANDS,
        "changes": changes,
        "warnings": warnings,
        "errors": errors,
        "can_apply": not errors,
    }
