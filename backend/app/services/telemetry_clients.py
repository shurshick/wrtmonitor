from __future__ import annotations

from typing import Any

from .telemetry_common import (
    _optional_nonnegative_int,
)


def normalize_clients_summary(payload: dict[str, Any]) -> dict[str, Any]:
    confirmed_neighbour_states = {"REACHABLE", "DELAY", "PROBE"}
    recent_neighbour_states = {"STALE"}
    offline_neighbour_states = {"FAILED", "INCOMPLETE"}
    preferred_neighbour_states = confirmed_neighbour_states | recent_neighbour_states
    clients = payload.get("clients") or {}
    traffic_source = clients.get("traffic") or {}
    dhcp = clients.get("dhcp") or payload.get("dhcp") or {}
    leases = dhcp.get("leases") or []
    static_leases = dhcp.get("static_leases") or []
    neighbours = clients.get("neighbours") or []
    by_mac: dict[str, dict[str, Any]] = {}

    for lease in static_leases:
        if not isinstance(lease, dict):
            continue
        mac = str(lease.get("mac") or "").lower()
        if not mac:
            continue
        by_mac[mac] = {
            "mac": mac,
            "ip": lease.get("ip"),
            "hostname": lease.get("hostname") or None,
            "interface": None,
            "state": "reserved",
            "source": "static-dhcp",
            "expires": None,
            "is_static": True,
            "vendor": lease.get("vendor"),
            "rx_bytes": lease.get("rx_bytes"),
            "tx_bytes": lease.get("tx_bytes"),
        }

    for lease in leases:
        if not isinstance(lease, dict):
            continue
        mac = str(lease.get("mac") or "").lower()
        if not mac:
            continue
        item = by_mac.setdefault(
            mac,
            {
                "mac": mac,
                "ip": lease.get("ip"),
                "hostname": None,
                "interface": None,
                "state": "leased",
                "source": "dhcp",
                "expires": lease.get("expires"),
                "is_static": False,
                "vendor": lease.get("vendor"),
                "rx_bytes": lease.get("rx_bytes"),
                "tx_bytes": lease.get("tx_bytes"),
            },
        )
        item["ip"] = lease.get("ip") or item.get("ip")
        item["hostname"] = (
            lease.get("hostname")
            if lease.get("hostname") not in (None, "", "*")
            else item.get("hostname")
        )
        item["expires"] = lease.get("expires") or item.get("expires")
        item["vendor"] = lease.get("vendor") or item.get("vendor")
        item["rx_bytes"] = lease.get("rx_bytes") or item.get("rx_bytes")
        item["tx_bytes"] = lease.get("tx_bytes") or item.get("tx_bytes")

    for neighbour in neighbours:
        if not isinstance(neighbour, dict):
            continue
        mac = str(neighbour.get("mac") or "").lower()
        if not mac:
            continue
        item = by_mac.setdefault(
            mac,
            {
                "mac": mac,
                "ip": neighbour.get("ip"),
                "hostname": None,
                "interface": None,
                "state": None,
                "source": "neighbour",
                "expires": None,
                "is_static": False,
                "vendor": neighbour.get("vendor"),
                "rx_bytes": neighbour.get("rx_bytes"),
                "tx_bytes": neighbour.get("tx_bytes"),
            },
        )
        item["ip"] = neighbour.get("ip") or item.get("ip")
        item["interface"] = neighbour.get("interface") or item.get("interface")
        current_state = str(item.get("state") or "").upper()
        candidate_state = str(neighbour.get("state") or "").upper()
        if candidate_state in preferred_neighbour_states or (
            current_state not in preferred_neighbour_states and candidate_state
        ):
            item["state"] = candidate_state
        item["vendor"] = neighbour.get("vendor") or item.get("vendor")
        item["rx_bytes"] = neighbour.get("rx_bytes") or item.get("rx_bytes")
        item["tx_bytes"] = neighbour.get("tx_bytes") or item.get("tx_bytes")
        if item.get("source") in {"dhcp", "static-dhcp"}:
            item["source"] = "dhcp+neighbour"

    wifi = payload.get("wifi") or {}
    for station_group in wifi.get("stations") or []:
        if not isinstance(station_group, dict):
            continue
        station_clients = station_group.get("clients") or {}
        if not isinstance(station_clients, dict):
            continue
        for station_mac, details in station_clients.items():
            mac = str(station_mac or "").lower()
            if not mac or not isinstance(details, dict):
                continue
            item = by_mac.setdefault(
                mac,
                {
                    "mac": mac,
                    "ip": None,
                    "hostname": None,
                    "interface": None,
                    "state": None,
                    "source": "wifi",
                    "expires": None,
                    "is_static": False,
                    "vendor": details.get("vendor"),
                    "rx_bytes": details.get("rx_bytes"),
                    "tx_bytes": details.get("tx_bytes"),
                },
            )
            item["interface"] = station_group.get("interface") or item.get("interface")
            item["state"] = "wifi"
            item["connection_type"] = "wifi"
            item["ssid"] = station_group.get("ssid")
            item["band"] = station_group.get("band")
            item["signal"] = details.get("signal", details.get("avg_ack_signal"))
            if item.get("source") != "wifi":
                item["source"] = f"{item.get('source') or 'client'}+wifi"

    for item in by_mac.values():
        state = str(item.get("state") or "").upper()
        if state == "WIFI":
            item["presence_evidence"] = "confirmed"
            item["presence_source"] = "wifi_station"
        elif state in confirmed_neighbour_states:
            item["presence_evidence"] = "confirmed"
            item["presence_source"] = "neighbour_active"
        elif state in recent_neighbour_states:
            item["presence_evidence"] = "recent"
            item["presence_source"] = "neighbour_stale"
        elif state in offline_neighbour_states:
            item["presence_evidence"] = "offline"
            item["presence_source"] = "neighbour_failed"
        else:
            item["presence_evidence"] = "unknown"
            item["presence_source"] = None

    items = sorted(
        by_mac.values(),
        key=lambda item: (str(item.get("hostname") or "~"), str(item.get("ip") or "")),
    )
    online_count = sum(
        1 for item in items if item.get("presence_evidence") == "confirmed"
    )
    recent_count = sum(1 for item in items if item.get("presence_evidence") == "recent")
    traffic_available = bool(traffic_source.get("available")) or any(
        item.get("rx_bytes") is not None or item.get("tx_bytes") is not None
        for item in items
    )
    return {
        "count": len(items),
        "online_count": online_count,
        "recent_count": recent_count,
        "traffic_available": traffic_available,
        "traffic_status": str(traffic_source.get("status") or "unknown"),
        "traffic_diagnostics": {
            "installed": bool(traffic_source.get("installed")),
            "service": str(traffic_source.get("service") or "unknown"),
            "records": _optional_nonnegative_int(traffic_source.get("records")),
            "recovery_attempted": bool(traffic_source.get("recovery_attempted")),
            "error": str(traffic_source.get("error") or ""),
        },
        "items": items,
    }


__all__ = ["normalize_clients_summary"]
