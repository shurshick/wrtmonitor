from __future__ import annotations

from typing import Any

from ..management_options import (
    NETMASK_OPTIONS,
    TIMEZONE_OPTIONS,
    WIFI_CHANNELS,
    WIFI_COUNTRIES,
)
from .telemetry import normalize_network_summary, normalize_wifi_summary


def _strings(values: Any) -> list[str]:
    if not isinstance(values, list):
        return []
    return sorted({str(value) for value in values if str(value).strip()})


def build_management_options(payload: dict[str, Any]) -> dict[str, Any]:
    raw_network = payload.get("network") or {}
    raw_wifi = payload.get("wifi") or {}
    network = normalize_network_summary(payload)
    wifi = normalize_wifi_summary(payload)
    interfaces = network.get("interfaces") or []
    topology = network.get("topology") or raw_network.get("topology") or {}
    radios = wifi.get("radios") or []
    raw_radios = {
        str(item.get("id")): item
        for item in raw_wifi.get("radios") or []
        if isinstance(item, dict) and item.get("id")
    }

    interface_names = sorted(
        {
            str(value)
            for item in interfaces
            if isinstance(item, dict)
            for value in (item.get("interface"), item.get("device"))
            if value
        }
    )
    firewall_zones = sorted(
        {
            str(item.get("name"))
            for item in network.get("firewall_zones")
            or raw_network.get("firewall_zones")
            or []
            if isinstance(item, dict) and item.get("name")
        }
    )
    bridges = sorted(
        {
            str(item.get("name"))
            for item in topology.get("bridges") or []
            if isinstance(item, dict) and item.get("name")
        }
    )
    networks = sorted(
        {
            str(item.get("interface"))
            for item in interfaces
            if isinstance(item, dict) and item.get("interface")
        }
    )
    wifi_radios = []
    observed_countries: set[str] = set()
    for index, item in enumerate(radios):
        if not isinstance(item, dict):
            continue
        country = str(item.get("country") or "")
        if country:
            observed_countries.add(country)
        raw_radio = raw_radios.get(str(item.get("id") or ""), {})
        supported_channels = _strings(
            item.get("supported_channels") or raw_radio.get("supported_channels")
        )
        current_channel = str(item.get("channel") or "")
        if current_channel and current_channel not in supported_channels:
            supported_channels.append(current_channel)
        wifi_radios.append(
            {
                "id": str(item.get("id") or f"radio{index}"),
                "name": str(item.get("name") or item.get("id") or f"radio{index}"),
                "band": str(item.get("band") or ""),
                "channel": current_channel,
                "country": country,
                "htmode": str(item.get("htmode") or ""),
                "supported_channels": sorted(
                    supported_channels,
                    key=lambda value: (
                        value != "auto",
                        int(value) if value.isdigit() else 9999,
                    ),
                ),
            }
        )

    return {
        "source": "router-telemetry",
        "interfaces": interface_names,
        "networks": networks,
        "bridges": bridges,
        "firewall_zones": firewall_zones,
        "wifi_radios": wifi_radios,
        "catalogs": {
            "netmasks": [
                {"value": mask, "prefix": prefix} for mask, prefix in NETMASK_OPTIONS
            ],
            "timezones": [
                {"zonename": name, "timezone": timezone, "label": label}
                for name, timezone, label in TIMEZONE_OPTIONS
            ],
            "wifi_countries": [
                {"value": code, "label": label, "observed": code in observed_countries}
                for code, label in WIFI_COUNTRIES
            ],
            "wifi_channels_fallback": list(WIFI_CHANNELS),
        },
    }


__all__ = ["build_management_options"]
