from __future__ import annotations

from ipaddress import IPv4Network
from typing import Any

from .telemetry_common import (
    _optional_nonnegative_int,
)


def normalize_network_summary(payload: dict[str, Any]) -> dict[str, Any]:
    network = payload.get("network") or {}
    interfaces = network.get("interfaces") or network.get("interface") or []
    normalized_interfaces: list[dict[str, Any]] = []
    for item in interfaces:
        if not isinstance(item, dict):
            continue
        ipv4_addresses = (
            item.get("ipv4_details")
            or item.get("ipv4-address")
            or item.get("ipv4")
            or []
        )
        ipv6_addresses = item.get("ipv6-address") or item.get("ipv6") or []
        route = item.get("route") or []
        dns_servers = item.get("dns-server") or item.get("dns") or []
        normalized_ipv4: list[str] = []
        normalized_ipv4_details: list[dict[str, Any]] = []
        for address in ipv4_addresses:
            if isinstance(address, dict):
                value = address.get("address")
                prefix_length = address.get("prefix_length", address.get("mask"))
                netmask = address.get("netmask")
            else:
                value = address
                prefix_length = None
                netmask = None
            if not value:
                continue
            value = str(value)
            try:
                prefix = int(prefix_length) if prefix_length is not None else None
            except (TypeError, ValueError):
                prefix = None
            if not netmask and prefix is not None and 0 <= prefix <= 32:
                netmask = str(IPv4Network(f"0.0.0.0/{prefix}").netmask)
            normalized_ipv4.append(value)
            normalized_ipv4_details.append(
                {
                    "address": value,
                    "prefix_length": prefix,
                    "netmask": str(netmask) if netmask else None,
                }
            )
        interface_netmask = item.get("netmask") or next(
            (
                address["netmask"]
                for address in normalized_ipv4_details
                if address.get("netmask")
            ),
            None,
        )
        normalized_interfaces.append(
            {
                "interface": item.get("interface") or item.get("name"),
                "up": item.get("up"),
                "proto": item.get("proto"),
                "device": item.get("l3_device") or item.get("device"),
                "ipv4": normalized_ipv4,
                "ipv4_details": normalized_ipv4_details,
                "netmask": interface_netmask,
                "ipv6": [
                    str(
                        address.get("address") if isinstance(address, dict) else address
                    )
                    for address in ipv6_addresses
                    if (isinstance(address, dict) and address.get("address"))
                    or (not isinstance(address, dict) and address)
                ],
                "ip6assign": str(item.get("ip6assign") or ""),
                "ip6hint": str(item.get("ip6hint") or ""),
                "gateway": item.get("gateway")
                or next(
                    (
                        entry.get("nexthop")
                        for entry in route
                        if isinstance(entry, dict) and entry.get("target") == "0.0.0.0"
                    ),
                    None,
                ),
                "dns": [str(server) for server in dns_servers if server],
                "errors": item.get("errors") or [],
            }
        )
    perimeter = payload.get("perimeter") or {}
    mwan3 = perimeter.get("mwan3") or {}
    if not isinstance(mwan3, dict):
        mwan3 = {}
    mwan_members = [
        {
            "role": str(item.get("role") or ""),
            "interface": str(item.get("interface") or ""),
            "metric": _optional_nonnegative_int(item.get("metric")),
            "track_ips": [str(value) for value in item.get("track_ips") or []],
            "interval": _optional_nonnegative_int(item.get("interval")),
            "down": _optional_nonnegative_int(item.get("down")),
            "up": _optional_nonnegative_int(item.get("up")),
        }
        for item in mwan3.get("members") or []
        if isinstance(item, dict) and item.get("interface")
    ]
    return {
        "interfaces": normalized_interfaces,
        "topology": network.get("topology")
        or {"segments": [], "bridges": [], "vlans": []},
        "dns_privacy": network.get("dns_privacy"),
        "routes": perimeter.get("routes") or [],
        "firewall_zones": perimeter.get("firewall_zones") or [],
        "firewall_forwardings": perimeter.get("firewall_forwardings") or [],
        "firewall_rules": perimeter.get("firewall_rules") or [],
        "firewall_redirects": perimeter.get("firewall_redirects") or [],
        "mwan3": {
            "installed": bool(mwan3.get("installed", False)),
            "service": str(mwan3.get("service") or "unavailable"),
            "enabled": bool(mwan3.get("enabled", False)),
            "members": mwan_members,
            "status": str(mwan3.get("status") or ""),
        },
        "ddns": perimeter.get("ddns"),
        "upnp": perimeter.get("upnp"),
    }


__all__ = ["normalize_network_summary"]
