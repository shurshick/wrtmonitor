from __future__ import annotations

from datetime import UTC, datetime, timedelta
from ipaddress import IPv4Network
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ..models import DeviceTelemetry, DeviceTelemetryMetric


TELEMETRY_STALE_SECONDS = 5 * 60
TELEMETRY_WINDOWS = {
    "live": (timedelta(hours=2), 120),
    "24h": (timedelta(hours=24), 288),
    "7d": (timedelta(days=7), 336),
    "30d": (timedelta(days=30), 360),
}


def cleanup_device_telemetry(db: Session, device_id: UUID, keep: int) -> None:
    old_ids = [
        row[0]
        for row in db.execute(
            select(DeviceTelemetry.id)
            .where(DeviceTelemetry.device_id == device_id)
            .order_by(DeviceTelemetry.created_at.desc())
            .offset(keep)
        ).all()
    ]
    if old_ids:
        db.execute(delete(DeviceTelemetry).where(DeviceTelemetry.id.in_(old_ids)))


def record_device_telemetry_metric(
    db: Session, device_id: UUID, payload: dict[str, Any], created_at: datetime
) -> DeviceTelemetryMetric:
    summary = build_telemetry_summary(payload)
    rx_bytes = _safe_int(summary.get("traffic_rx_bytes"))
    tx_bytes = _safe_int(summary.get("traffic_tx_bytes"))
    previous = db.scalars(
        select(DeviceTelemetryMetric)
        .where(DeviceTelemetryMetric.device_id == device_id)
        .order_by(DeviceTelemetryMetric.created_at.desc())
        .limit(1)
    ).first()
    rx_bps = tx_bps = 0
    if previous is not None:
        elapsed = (created_at - previous.created_at).total_seconds()
        if elapsed > 0:
            if rx_bytes >= previous.rx_bytes:
                rx_bps = round((rx_bytes - previous.rx_bytes) * 8 / elapsed)
            if tx_bytes >= previous.tx_bytes:
                tx_bps = round((tx_bytes - previous.tx_bytes) * 8 / elapsed)
    memory_total = _safe_int(summary.get("memory_total_mb"))
    memory_available = _safe_int(summary.get("memory_available_mb"))
    network = normalize_network_summary(payload)
    wifi = normalize_wifi_summary(payload)
    metric = DeviceTelemetryMetric(
        id=uuid4(),
        device_id=device_id,
        rx_bps=rx_bps,
        tx_bps=tx_bps,
        rx_bytes=rx_bytes,
        tx_bytes=tx_bytes,
        load_1m=_safe_float(summary.get("load_1m")),
        memory_percent=round(
            100 * max(0, memory_total - memory_available) / memory_total, 1
        )
        if memory_total
        else 0,
        client_count=_safe_int(summary.get("client_count")),
        interfaces={"items": network.get("interfaces") or []},
        wifi={
            "radios": wifi.get("radios") or [],
            "station_count": wifi.get("station_count") or 0,
        },
        created_at=created_at,
    )
    db.add(metric)
    return metric


def cleanup_device_telemetry_metrics(
    db: Session, device_id: UUID, retention_days: int
) -> None:
    cutoff = datetime.now(UTC) - timedelta(days=max(1, retention_days))
    db.execute(
        delete(DeviceTelemetryMetric).where(
            DeviceTelemetryMetric.device_id == device_id,
            DeviceTelemetryMetric.created_at < cutoff,
        )
    )


def device_telemetry_history(
    db: Session,
    device_id: UUID,
    limit: int = 60,
    range_name: str | None = None,
) -> list[dict[str, Any]]:
    if range_name:
        window, target_points = TELEMETRY_WINDOWS.get(
            range_name, TELEMETRY_WINDOWS["live"]
        )
        rows = list(
            db.scalars(
                select(DeviceTelemetryMetric)
                .where(
                    DeviceTelemetryMetric.device_id == device_id,
                    DeviceTelemetryMetric.created_at >= datetime.now(UTC) - window,
                )
                .order_by(DeviceTelemetryMetric.created_at.asc())
            ).all()
        )
        if rows and hasattr(rows[0], "rx_bps"):
            return downsample_telemetry_metrics(rows, target_points)
    metric_rows = list(
        reversed(
            list(
                db.scalars(
                    select(DeviceTelemetryMetric)
                    .where(DeviceTelemetryMetric.device_id == device_id)
                    .order_by(DeviceTelemetryMetric.created_at.desc())
                    .limit(max(2, min(limit, 360)))
                ).all()
            )
        )
    )
    if metric_rows and hasattr(metric_rows[0], "rx_bps"):
        return [metric_history_point(row) for row in metric_rows]
    rows = list(
        db.scalars(
            select(DeviceTelemetry)
            .where(DeviceTelemetry.device_id == device_id)
            .order_by(DeviceTelemetry.created_at.desc())
            .limit(max(2, min(limit, 120)))
        ).all()
    )
    return build_telemetry_history(reversed(rows))


def metric_history_point(row: DeviceTelemetryMetric) -> dict[str, Any]:
    return {
        "created_at": row.created_at.isoformat(),
        "rx_bps": row.rx_bps,
        "tx_bps": row.tx_bps,
        "rx_bytes": row.rx_bytes,
        "tx_bytes": row.tx_bytes,
        "load_1m": round(row.load_1m, 2),
        "memory_percent": round(row.memory_percent, 1),
        "client_count": row.client_count,
    }


def downsample_telemetry_metrics(
    rows: list[DeviceTelemetryMetric], target_points: int
) -> list[dict[str, Any]]:
    if len(rows) <= target_points:
        return [metric_history_point(row) for row in rows]
    bucket_size = max(1, (len(rows) + target_points - 1) // target_points)
    points: list[dict[str, Any]] = []
    for start in range(0, len(rows), bucket_size):
        bucket = rows[start : start + bucket_size]
        last = bucket[-1]
        count = len(bucket)
        points.append(
            {
                "created_at": last.created_at.isoformat(),
                "rx_bps": round(sum(row.rx_bps for row in bucket) / count),
                "tx_bps": round(sum(row.tx_bps for row in bucket) / count),
                "rx_bytes": last.rx_bytes,
                "tx_bytes": last.tx_bytes,
                "load_1m": round(sum(row.load_1m for row in bucket) / count, 2),
                "memory_percent": round(
                    sum(row.memory_percent for row in bucket) / count, 1
                ),
                "client_count": round(sum(row.client_count for row in bucket) / count),
            }
        )
    return points


def telemetry_alerts(
    payload: dict[str, Any] | None, age_seconds: int | None
) -> list[dict[str, str]]:
    if not payload:
        return [
            {
                "level": "warning",
                "code": "no_data",
                "message": "Telemetry ещё не получена",
            }
        ]
    alerts: list[dict[str, str]] = []
    if age_seconds is not None and age_seconds > TELEMETRY_STALE_SECONDS:
        alerts.append(
            {
                "level": "critical",
                "code": "stale",
                "message": "Связь с роутером потеряна",
            }
        )
    memory = (payload.get("system") or {}).get("memory") or {}
    memory_total = _safe_int(memory.get("total_kb"))
    memory_available = _safe_int(memory.get("available_kb", memory.get("free_kb")))
    memory_percent = (
        100 * max(0, memory_total - memory_available) / memory_total
        if memory_total
        else 0
    )
    if memory_percent >= 90:
        alerts.append(
            {
                "level": "warning",
                "code": "memory",
                "message": "Использовано более 90% памяти",
            }
        )
    network = normalize_network_summary(payload)
    wan = next(
        (
            item
            for item in network.get("interfaces") or []
            if item.get("interface") == "wan"
        ),
        None,
    )
    if wan is not None and not wan.get("up"):
        alerts.append(
            {"level": "warning", "code": "wan", "message": "WAN-интерфейс не подключён"}
        )
    return alerts


def build_telemetry_history(
    rows: Any,
) -> list[dict[str, Any]]:
    points: list[dict[str, Any]] = []
    previous: tuple[datetime, int, int] | None = None
    for row in rows:
        payload = row.payload if isinstance(row.payload, dict) else {}
        summary = build_telemetry_summary(payload)
        rx_bytes = _safe_int(summary.get("traffic_rx_bytes"))
        tx_bytes = _safe_int(summary.get("traffic_tx_bytes"))
        rx_bps = tx_bps = 0
        if previous is not None:
            previous_at, previous_rx, previous_tx = previous
            elapsed = (row.created_at - previous_at).total_seconds()
            if elapsed > 0:
                if rx_bytes >= previous_rx:
                    rx_bps = round((rx_bytes - previous_rx) * 8 / elapsed)
                if tx_bytes >= previous_tx:
                    tx_bps = round((tx_bytes - previous_tx) * 8 / elapsed)
        memory_total = _safe_int(summary.get("memory_total_mb"))
        memory_available = _safe_int(summary.get("memory_available_mb"))
        points.append(
            {
                "created_at": row.created_at.isoformat(),
                "rx_bps": rx_bps,
                "tx_bps": tx_bps,
                "rx_bytes": rx_bytes,
                "tx_bytes": tx_bytes,
                "load_1m": _safe_float(summary.get("load_1m")),
                "memory_percent": round(
                    100 * max(0, memory_total - memory_available) / memory_total, 1
                )
                if memory_total
                else 0,
                "client_count": _safe_int(summary.get("client_count")),
            }
        )
        previous = (row.created_at, rx_bytes, tx_bytes)
    return points


def _safe_int(value: Any) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def _safe_float(value: Any) -> float:
    try:
        return round(max(0.0, float(value or 0)), 2)
    except (TypeError, ValueError):
        return 0.0


def extract_agent_status(payload: dict[str, Any]) -> dict[str, Any]:
    agent = payload.get("agent") or {}
    capabilities = extract_agent_capabilities(payload)
    return {
        "version": agent.get("version"),
        "status": agent.get("status", "running"),
        "platform": agent.get("platform", "openwrt"),
        "capabilities_version": agent.get("capabilities_version"),
        "auto_update_enabled": bool(agent.get("auto_update_enabled", False)),
        "telemetry_interval_seconds": agent.get("telemetry_interval_seconds"),
        "last_update_status": agent.get("last_update_status") or "",
        "last_update_error": agent.get("last_update_error") or "",
        "last_update_check": agent.get("last_update_check") or "",
        "last_successful_update": agent.get("last_successful_update") or "",
        "available_version": agent.get("available_version") or "",
        "rollback_available": bool(agent.get("backup_available", False)),
        "backup_available": bool(agent.get("backup_available", False)),
        "update_source": agent.get("update_source") or "",
        "capabilities": capabilities,
        "capability_details": extract_agent_capability_details(payload),
    }


def extract_agent_capabilities(payload: dict[str, Any]) -> dict[str, bool]:
    agent = payload.get("agent") or {}
    capabilities = agent.get("capabilities") or {}
    if not isinstance(capabilities, dict):
        return {}
    return {str(key): bool(value) for key, value in capabilities.items()}


def extract_agent_capability_details(
    payload: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    agent = payload.get("agent") or {}
    details = agent.get("capability_details") or {}
    if not isinstance(details, dict):
        return {}
    normalized: dict[str, dict[str, Any]] = {}
    for key, detail in details.items():
        if not isinstance(detail, dict):
            continue
        normalized[str(key)] = {
            "supported": bool(detail.get("supported", False)),
            "reason": str(detail.get("reason") or ""),
        }
    return normalized


def normalize_maintenance_summary(payload: dict[str, Any]) -> dict[str, Any]:
    maintenance = payload.get("maintenance") or {}
    if not isinstance(maintenance, dict):
        maintenance = {}
    packages = maintenance.get("packages") or {}
    if not isinstance(packages, dict):
        packages = {}
    return {
        "package_manager": str(packages.get("manager") or ""),
        "installed_packages": int(
            packages.get("installed", maintenance.get("installed_packages")) or 0
        ),
        "upgradable_packages": int(
            packages.get("upgradable", maintenance.get("upgradable_packages")) or 0
        ),
        "installed_items": [
            item
            for item in packages.get("installed_items") or []
            if isinstance(item, dict)
        ],
        "upgradable_items": [
            item
            for item in packages.get("upgradable_items") or []
            if isinstance(item, dict)
        ],
        "cron_entries": int(maintenance.get("cron_entries") or 0),
        "recovery_mode": bool(maintenance.get("recovery_mode", False)),
        "staged_firmware_sha256": str(maintenance.get("staged_firmware_sha256") or ""),
    }


def normalize_wifi_summary(payload: dict[str, Any]) -> dict[str, Any]:
    wifi = payload.get("wifi") or {}
    radios = wifi.get("radios") or []
    normalized_stations: list[dict[str, Any]] = []
    for station_group in wifi.get("stations") or []:
        if not isinstance(station_group, dict):
            continue
        clients = station_group.get("clients") or {}
        if not isinstance(clients, dict):
            continue
        for mac, details in clients.items():
            if not isinstance(details, dict):
                continue
            rx = details.get("rx_rate") or details.get("rx") or {}
            tx = details.get("tx_rate") or details.get("tx") or {}
            airtime = details.get("airtime") or {}
            airtime_rx_us = airtime.get("rx") if isinstance(airtime, dict) else None
            airtime_tx_us = airtime.get("tx") if isinstance(airtime, dict) else None
            normalized_stations.append(
                {
                    "mac": str(mac).lower(),
                    "interface": station_group.get("interface"),
                    "ssid": station_group.get("ssid"),
                    "band": station_group.get("band"),
                    "signal": details.get("signal", details.get("avg_ack_signal")),
                    "noise": details.get("noise"),
                    "rx_bitrate": _station_rate(rx),
                    "tx_bitrate": _station_rate(tx),
                    "connected_seconds": details.get("connected_time"),
                    "airtime_rx_us": _optional_nonnegative_int(airtime_rx_us),
                    "airtime_tx_us": _optional_nonnegative_int(airtime_tx_us),
                    "airtime_weight": details.get("airtime_weight"),
                }
            )
    normalized_radios: list[dict[str, Any]] = []
    for index, radio in enumerate(radios):
        if not isinstance(radio, dict):
            continue
        interfaces = radio.get("interfaces") or []
        normalized_interfaces: list[dict[str, Any]] = []
        for iface_index, iface in enumerate(interfaces):
            if not isinstance(iface, dict):
                continue
            normalized_interfaces.append(
                {
                    "id": iface.get("id")
                    or f"default_{radio.get('name', f'radio{index}')}_{iface_index}",
                    "index": iface.get("index", iface_index),
                    "ssid": iface.get("ssid"),
                    "enabled": bool(iface.get("enabled", True)),
                    "encryption": iface.get("encryption"),
                    "mode": iface.get("mode"),
                    "network": iface.get("network"),
                    "hidden": bool(iface.get("hidden", False)),
                    "isolate": bool(iface.get("isolate", False)),
                    "ieee80211r": bool(iface.get("ieee80211r", False)),
                    "ieee80211k": bool(iface.get("ieee80211k", False)),
                    "bss_transition": bool(iface.get("bss_transition", False)),
                    "mobility_domain": iface.get("mobility_domain"),
                    "mesh_id": iface.get("mesh_id"),
                }
            )
        if not normalized_interfaces and radio.get("ssid"):
            ssids = radio.get("ssid")
            if not isinstance(ssids, list):
                ssids = [ssids]
            for iface_index, ssid in enumerate(ssids):
                normalized_interfaces.append(
                    {
                        "id": f"default_{radio.get('name', f'radio{index}')}_{iface_index}",
                        "index": iface_index,
                        "ssid": ssid,
                        "enabled": bool(radio.get("up", True)),
                        "encryption": radio.get("encryption"),
                    }
                )
        normalized_radios.append(
            {
                "id": radio.get("id") or radio.get("name") or f"radio{index}",
                "name": radio.get("name") or f"radio{index}",
                "up": bool(radio.get("up", False)),
                "disabled": bool(radio.get("disabled", False)),
                "band": radio.get("band"),
                "channel": radio.get("channel"),
                "country": radio.get("country"),
                "htmode": radio.get("htmode"),
                "txpower": radio.get("txpower"),
                "interfaces": normalized_interfaces,
                "ssid": radio.get("ssid") or [],
                "encryption": radio.get("encryption"),
                "schedule": radio.get("schedule") or {"enabled": False},
            }
        )
    has_station_rates = any(
        item.get("rx_bitrate") is not None or item.get("tx_bitrate") is not None
        for item in normalized_stations
    )
    has_station_airtime = any(
        item.get("airtime_rx_us") is not None or item.get("airtime_tx_us") is not None
        for item in normalized_stations
    )
    return {
        "available": bool(wifi.get("available", False)),
        "radios": normalized_radios,
        "stations": normalized_stations,
        "station_count": len(normalized_stations),
        "has_station_rates": has_station_rates,
        "has_station_airtime": has_station_airtime,
    }


def _optional_nonnegative_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return None


def _station_rate(value: Any) -> int | float | str | None:
    if isinstance(value, dict):
        value = value.get("rate", value.get("bitrate", value.get("bitrate_kbps")))
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return value if value > 0 else None
    return str(value)


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
                "up": bool(item.get("up", False)),
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
    return {
        "interfaces": normalized_interfaces,
        "routes": perimeter.get("routes") or [],
        "firewall_zones": perimeter.get("firewall_zones") or [],
        "firewall_forwardings": perimeter.get("firewall_forwardings") or [],
        "firewall_rules": perimeter.get("firewall_rules") or [],
        "mwan3": perimeter.get("mwan3") or {"service": "unavailable"},
        "ddns": perimeter.get("ddns") or {"service": "unavailable", "services": []},
        "upnp": perimeter.get("upnp") or {"service": "unavailable", "mappings": []},
    }


def normalize_vpn_summary(payload: dict[str, Any]) -> dict[str, Any]:
    vpn = payload.get("vpn") or {}
    wireguard = vpn.get("wireguard") or {}
    interfaces: list[dict[str, Any]] = []
    for interface in wireguard.get("interfaces") or []:
        if not isinstance(interface, dict):
            continue
        peers = [
            peer for peer in interface.get("peers") or [] if isinstance(peer, dict)
        ]
        interfaces.append(
            {
                "name": interface.get("name"),
                "public_key": interface.get("public_key"),
                "listen_port": interface.get("listen_port"),
                "peers": peers,
                "peer_count": len(peers),
                "rx_bytes": sum(int(peer.get("rx_bytes") or 0) for peer in peers),
                "tx_bytes": sum(int(peer.get("tx_bytes") or 0) for peer in peers),
            }
        )
    openvpn = vpn.get("openvpn") or {}
    policy = vpn.get("policy") or {}
    return {
        "wireguard": {"interfaces": interfaces},
        "openvpn": {
            "service": openvpn.get("service") or "unavailable",
            "clients": openvpn.get("clients") or [],
        },
        "policy": {
            "service": policy.get("service") or "unavailable",
            "policies": policy.get("policies") or [],
        },
    }


def normalize_clients_summary(payload: dict[str, Any]) -> dict[str, Any]:
    confirmed_neighbour_states = {"REACHABLE", "DELAY", "PROBE"}
    recent_neighbour_states = {"STALE"}
    offline_neighbour_states = {"FAILED", "INCOMPLETE"}
    preferred_neighbour_states = confirmed_neighbour_states | recent_neighbour_states
    clients = payload.get("clients") or {}
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
    traffic_available = any(
        item.get("rx_bytes") is not None or item.get("tx_bytes") is not None
        for item in items
    )
    return {
        "count": len(items),
        "online_count": online_count,
        "recent_count": recent_count,
        "traffic_available": traffic_available,
        "items": items,
    }


def normalize_services_summary(payload: dict[str, Any]) -> dict[str, str]:
    services = (payload.get("system") or {}).get("services") or {}
    if not isinstance(services, dict):
        return {}
    return {str(name): str(status) for name, status in services.items()}


def normalize_system_summary(payload: dict[str, Any]) -> dict[str, Any]:
    system = payload.get("system") or {}
    conntrack = system.get("conntrack") or {}
    time_config = system.get("time") or {}
    return {
        "hostname": system.get("hostname"),
        "kernel": system.get("kernel"),
        "local_time": system.get("local_time"),
        "uptime_seconds": system.get("uptime"),
        "load_1m": system.get("load"),
        "load_5m": system.get("load_5m"),
        "load_15m": system.get("load_15m"),
        "conntrack_count": conntrack.get("count"),
        "conntrack_max": conntrack.get("max"),
        "zonename": time_config.get("zonename"),
        "timezone": time_config.get("timezone"),
        "ntp_enabled": bool(time_config.get("ntp_enabled", False)),
        "ntp_servers": time_config.get("ntp_servers") or [],
        "services": normalize_services_summary(payload),
    }


def build_telemetry_summary(payload: dict[str, Any]) -> dict[str, Any]:
    system = payload.get("system") or {}
    memory = system.get("memory") or {}
    cpu = payload.get("cpu") or {}
    storage = payload.get("storage") or {}
    thermal = payload.get("thermal") or {}
    traffic = payload.get("traffic") or {}
    wifi = normalize_wifi_summary(payload)
    network = normalize_network_summary(payload)
    interfaces = network.get("interfaces") or []
    radios = wifi.get("radios") or []
    clients = normalize_clients_summary(payload)
    system_summary = normalize_system_summary(payload)
    return {
        "uptime_seconds": system.get("uptime"),
        "load_1m": system.get("load"),
        "memory_total_mb": int(memory.get("total_kb", 0) or 0) // 1024,
        "memory_available_mb": int(
            memory.get("available_kb", memory.get("free_kb", 0)) or 0
        )
        // 1024,
        "cpu_cores": cpu.get("cores"),
        "storage_total_mb": int(storage.get("total_kb", 0) or 0) // 1024,
        "storage_available_mb": int(storage.get("available_kb", 0) or 0) // 1024,
        "temperature_celsius": (thermal.get("milli_celsius") or 0) / 1000
        if thermal.get("available")
        else None,
        "traffic_rx_bytes": traffic.get("rx_bytes"),
        "traffic_tx_bytes": traffic.get("tx_bytes"),
        "wifi_available": bool(wifi.get("available", False)),
        "wifi_radio_count": len(radios),
        "network_interface_count": len(interfaces),
        "agent_capability_count": len(extract_agent_capabilities(payload)),
        "client_count": clients["online_count"],
        "hostname": system_summary.get("hostname"),
        "kernel": system_summary.get("kernel"),
        "conntrack_count": system_summary.get("conntrack_count"),
        "conntrack_max": system_summary.get("conntrack_max"),
    }
