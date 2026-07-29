from __future__ import annotations

from typing import Any

from .telemetry_common import (
    _kb_to_mb,
    _millidegrees_to_celsius,
    extract_agent_capabilities,
)
from .telemetry_wifi import normalize_wifi_summary
from .telemetry_network import normalize_network_summary
from .telemetry_clients import normalize_clients_summary
from .telemetry_system import normalize_system_summary


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
        "memory_total_mb": _kb_to_mb(memory.get("total_kb")),
        "memory_available_mb": _kb_to_mb(
            memory.get("available_kb", memory.get("free_kb"))
        ),
        "cpu_cores": cpu.get("cores"),
        "storage_total_mb": _kb_to_mb(storage.get("total_kb")),
        "storage_available_mb": _kb_to_mb(storage.get("available_kb")),
        "temperature_celsius": _millidegrees_to_celsius(
            thermal.get("milli_celsius") if thermal.get("available") else None
        ),
        "traffic_rx_bytes": traffic.get("rx_bytes"),
        "traffic_tx_bytes": traffic.get("tx_bytes"),
        "wifi_available": wifi.get("available"),
        "wifi_radio_count": len(radios) if payload.get("wifi") is not None else None,
        "network_interface_count": len(interfaces)
        if payload.get("network") is not None
        else None,
        "agent_capability_count": len(extract_agent_capabilities(payload)),
        "client_count": clients["online_count"],
        "hostname": system_summary.get("hostname"),
        "kernel": system_summary.get("kernel"),
        "conntrack_count": system_summary.get("conntrack_count"),
        "conntrack_max": system_summary.get("conntrack_max"),
    }


__all__ = ["build_telemetry_summary"]
