from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ..models import DeviceTelemetry


TELEMETRY_STALE_SECONDS = 5 * 60


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


def extract_agent_status(payload: dict[str, Any]) -> dict[str, Any]:
    agent = payload.get("agent") or {}
    capabilities = extract_agent_capabilities(payload)
    return {
        "version": agent.get("version"),
        "status": agent.get("status", "running"),
        "platform": agent.get("platform", "openwrt"),
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
    }


def extract_agent_capabilities(payload: dict[str, Any]) -> dict[str, bool]:
    agent = payload.get("agent") or {}
    capabilities = agent.get("capabilities") or {}
    if not isinstance(capabilities, dict):
        return {}
    return {str(key): bool(value) for key, value in capabilities.items()}


def normalize_wifi_summary(payload: dict[str, Any]) -> dict[str, Any]:
    wifi = payload.get("wifi") or {}
    radios = wifi.get("radios") or []
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
                "interfaces": normalized_interfaces,
                "ssid": radio.get("ssid") or [],
                "encryption": radio.get("encryption"),
            }
        )
    return {
        "available": bool(wifi.get("available", False)),
        "radios": normalized_radios,
    }


def normalize_network_summary(payload: dict[str, Any]) -> dict[str, Any]:
    network = payload.get("network") or {}
    interfaces = network.get("interfaces") or network.get("interface") or []
    normalized_interfaces: list[dict[str, Any]] = []
    for item in interfaces:
        if not isinstance(item, dict):
            continue
        ipv4_addresses = item.get("ipv4-address") or []
        route = item.get("route") or []
        dns_servers = item.get("dns-server") or []
        normalized_interfaces.append(
            {
                "interface": item.get("interface") or item.get("name"),
                "up": bool(item.get("up", False)),
                "proto": item.get("proto"),
                "device": item.get("l3_device") or item.get("device"),
                "ipv4": [
                    address.get("address")
                    for address in ipv4_addresses
                    if isinstance(address, dict) and address.get("address")
                ],
                "gateway": next(
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
    return {"interfaces": normalized_interfaces}


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
    }
