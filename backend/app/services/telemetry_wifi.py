from __future__ import annotations

from typing import Any

from .telemetry_common import (
    _optional_int,
    _optional_nonnegative_int,
    _optional_percent,
    _station_rate,
)


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
    normalized_networks: list[dict[str, Any]] = []
    for radio in radios:
        if not isinstance(radio, dict):
            continue
        interfaces = radio.get("interfaces") or []
        normalized_interfaces: list[dict[str, Any]] = []
        for iface in interfaces:
            if not isinstance(iface, dict):
                continue
            network_name = str(iface.get("network") or "")
            mode = str(iface.get("mode") or "")
            isolate = bool(iface.get("isolate", False))
            role = (
                "mesh"
                if mode == "mesh"
                else "guest"
                if isolate or "guest" in network_name.lower()
                else "primary"
                if mode == "ap" and network_name == "lan"
                else "additional"
            )
            normalized_iface = {
                "id": iface.get("id"),
                "index": iface.get("index"),
                "ssid": iface.get("ssid"),
                "enabled": iface.get("enabled"),
                "encryption": iface.get("encryption"),
                "mode": mode,
                "network": network_name,
                "role": role,
                "hidden": iface.get("hidden"),
                "isolate": iface.get("isolate"),
                "ieee80211r": iface.get("ieee80211r"),
                "ieee80211k": iface.get("ieee80211k"),
                "bss_transition": iface.get("bss_transition"),
                "mobility_domain": iface.get("mobility_domain"),
                "mesh_id": iface.get("mesh_id"),
            }
            normalized_interfaces.append(normalized_iface)
            normalized_networks.append(
                {
                    **normalized_iface,
                    "radio_id": radio.get("id") or radio.get("name"),
                    "band": radio.get("band"),
                }
            )
        survey = radio.get("survey") if isinstance(radio.get("survey"), dict) else {}
        runtime = radio.get("runtime") if isinstance(radio.get("runtime"), dict) else {}
        supported_channels = radio.get("supported_channels") or []
        if not isinstance(supported_channels, list):
            supported_channels = []
        normalized_radios.append(
            {
                "id": radio.get("id") or radio.get("name"),
                "name": radio.get("name"),
                "up": radio.get("up"),
                "configured_enabled": radio.get(
                    "configured_enabled", not bool(radio.get("disabled", False))
                ),
                "disabled": radio.get("disabled"),
                "runtime": {
                    "state": str(runtime.get("state") or "unsupported"),
                    "reason": str(runtime.get("reason") or ""),
                    "up": runtime.get("up"),
                    "pending": runtime.get("pending"),
                    "ifname": runtime.get("ifname"),
                },
                "band": radio.get("band"),
                "channel": radio.get("channel"),
                "country": radio.get("country"),
                "htmode": radio.get("htmode"),
                "txpower": radio.get("txpower"),
                "interfaces": normalized_interfaces,
                "ssid": radio.get("ssid"),
                "encryption": radio.get("encryption"),
                "schedule": radio.get("schedule"),
                "supported_channels": [str(item) for item in supported_channels],
                "survey": {
                    "state": str(survey.get("state") or "unsupported"),
                    "reason": str(survey.get("reason") or ""),
                    "interface": survey.get("interface"),
                    "frequency_mhz": _optional_nonnegative_int(
                        survey.get("frequency_mhz")
                    ),
                    "noise_dbm": _optional_int(survey.get("noise_dbm")),
                    "active_ms": _optional_nonnegative_int(survey.get("active_ms")),
                    "busy_ms": _optional_nonnegative_int(survey.get("busy_ms")),
                    "rx_ms": _optional_nonnegative_int(survey.get("rx_ms")),
                    "tx_ms": _optional_nonnegative_int(survey.get("tx_ms")),
                    "utilization_percent": _optional_percent(
                        survey.get("utilization_percent")
                    ),
                },
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
    for network in normalized_networks:
        network["station_count"] = sum(
            1
            for station in normalized_stations
            if (
                network.get("ssid")
                and station.get("ssid") == network.get("ssid")
                and (
                    not station.get("band")
                    or not network.get("band")
                    or station.get("band") == network.get("band")
                )
            )
        )
    available = wifi.get("available")
    state = str(
        wifi.get("state")
        or ("observed" if available is True or normalized_radios else "unsupported")
    )
    reason = str(
        wifi.get("reason") or ("no_wifi_radio" if state == "unsupported" else "")
    )
    return {
        "available": available,
        "state": state,
        "reason": reason,
        "radios": normalized_radios,
        "networks": normalized_networks,
        "network_count": len(normalized_networks),
        "stations": normalized_stations,
        "station_count": len(normalized_stations) if "stations" in wifi else None,
        "has_station_rates": has_station_rates if "stations" in wifi else None,
        "has_station_airtime": has_station_airtime if "stations" in wifi else None,
    }


__all__ = ["normalize_wifi_summary"]
