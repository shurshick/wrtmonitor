from __future__ import annotations

from datetime import UTC, datetime, timedelta
import base64
import binascii
from ipaddress import (
    IPv4Address,
    AddressValueError,
    ip_address,
    ip_interface,
    ip_network,
)
import re
from typing import Any, Callable
from urllib.parse import urlsplit
from uuid import UUID, uuid4

from fastapi import HTTPException
from sqlalchemy import and_, delete, or_, select, update
from sqlalchemy.orm import Session

from ..management_options import TIMEZONE_BY_NAME
from ..models import DeviceCommand, DeviceTelemetry
from .config_transactions import (
    attach_transaction_metadata,
    ensure_preflight_valid,
    is_transactional_command,
)


COMMAND_TTL = timedelta(minutes=5)
COMMAND_DELIVERY_LEASE = timedelta(seconds=45)
TERMINAL_STATUSES = {"success", "failed", "expired", "cancelled"}

ALLOWED_DIAGNOSTIC_CHECKS = {"server", "dns", "route", "wifi", "dependencies"}

COMMAND_REGISTRY: dict[str, dict[str, Any]] = {
    "router.reboot": {
        "risk_level": "level_3_reversible_config",
        "capability": "system.reboot",
        "requires_confirmation": True,
        "secret_fields": [],
    },
    "wifi.status": {
        "risk_level": "level_1_readonly",
        "capability": "wifi.read",
        "requires_confirmation": False,
        "secret_fields": [],
    },
    "wifi.set_enabled": {
        "risk_level": "level_3_reversible_config",
        "capability": "wifi.enable",
        "requires_confirmation": True,
        "secret_fields": [],
    },
    "wifi.set_ssid": {
        "risk_level": "level_3_reversible_config",
        "capability": "wifi.set_ssid",
        "requires_confirmation": True,
        "secret_fields": [],
    },
    "wifi.set_password": {
        "risk_level": "level_3_reversible_config",
        "capability": "wifi.set_password",
        "requires_confirmation": True,
        "secret_fields": ["password", "wifi_password", "key"],
    },
    "wifi.set_channel": {
        "risk_level": "level_3_reversible_config",
        "capability": "wifi.set_channel",
        "requires_confirmation": True,
        "secret_fields": [],
    },
    "wifi.set_country": {
        "risk_level": "level_3_reversible_config",
        "capability": "wifi.set_country",
        "requires_confirmation": True,
        "secret_fields": [],
    },
    "wifi.set_radio": {
        "risk_level": "level_3_reversible_config",
        "capability": "wifi.radio.configure",
        "requires_confirmation": True,
        "secret_fields": [],
    },
    "wifi.add_ssid": {
        "risk_level": "level_3_reversible_config",
        "capability": "wifi.manage_ssid",
        "requires_confirmation": True,
        "secret_fields": ["password", "key"],
    },
    "wifi.update_ssid": {
        "risk_level": "level_3_reversible_config",
        "capability": "wifi.manage_ssid",
        "requires_confirmation": True,
        "secret_fields": ["password", "key"],
    },
    "wifi.delete_ssid": {
        "risk_level": "level_3_reversible_config",
        "capability": "wifi.manage_ssid",
        "requires_confirmation": True,
        "secret_fields": [],
    },
    "wifi.set_schedule": {
        "risk_level": "level_3_reversible_config",
        "capability": "wifi.schedule",
        "requires_confirmation": True,
        "secret_fields": [],
    },
    "wifi.set_mesh": {
        "risk_level": "level_4_disruptive",
        "capability": "wifi.mesh",
        "requires_confirmation": True,
        "secret_fields": ["password", "key"],
    },
    "network.interfaces": {
        "risk_level": "level_1_readonly",
        "capability": "network.read",
        "requires_confirmation": False,
        "secret_fields": [],
    },
    "network.interface_restart": {
        "risk_level": "level_3_reversible_config",
        "capability": "network.interface_restart",
        "requires_confirmation": True,
        "secret_fields": [],
    },
    "network.restart": {
        "risk_level": "level_4_disruptive",
        "capability": "network.restart",
        "requires_confirmation": True,
        "secret_fields": [],
    },
    "network.set_wan": {
        "risk_level": "level_4_disruptive",
        "capability": "network.wan.configure",
        "requires_confirmation": True,
        "secret_fields": ["password"],
    },
    "network.set_lan": {
        "risk_level": "level_4_disruptive",
        "capability": "network.lan.configure",
        "requires_confirmation": True,
        "secret_fields": [],
    },
    "network.set_ipv6": {
        "risk_level": "level_4_disruptive",
        "capability": "network.ipv6.configure",
        "requires_confirmation": True,
        "secret_fields": [],
    },
    "network.set_multiwan": {
        "risk_level": "level_4_disruptive",
        "capability": "network.multiwan.configure",
        "requires_confirmation": True,
        "secret_fields": [],
    },
    "network.set_route": {
        "risk_level": "level_3_reversible_config",
        "capability": "network.routes.configure",
        "requires_confirmation": True,
        "secret_fields": [],
    },
    "network.delete_route": {
        "risk_level": "level_3_reversible_config",
        "capability": "network.routes.configure",
        "requires_confirmation": True,
        "secret_fields": [],
    },
    "network.set_ddns": {
        "risk_level": "level_3_reversible_config",
        "capability": "network.ddns.configure",
        "requires_confirmation": True,
        "secret_fields": ["password"],
    },
    "network.set_upnp": {
        "risk_level": "level_3_reversible_config",
        "capability": "firewall.upnp.configure",
        "requires_confirmation": True,
        "secret_fields": [],
    },
    "vpn.wireguard.set_interface": {
        "risk_level": "level_4_disruptive",
        "capability": "vpn.wireguard.configure",
        "requires_confirmation": True,
        "secret_fields": ["private_key"],
    },
    "vpn.wireguard.set_peer": {
        "risk_level": "level_3_reversible_config",
        "capability": "vpn.wireguard.configure",
        "requires_confirmation": True,
        "secret_fields": ["preshared_key"],
    },
    "vpn.wireguard.delete_peer": {
        "risk_level": "level_3_reversible_config",
        "capability": "vpn.wireguard.configure",
        "requires_confirmation": True,
        "secret_fields": [],
    },
    "vpn.wireguard.export_peer": {
        "risk_level": "level_1_readonly",
        "capability": "vpn.wireguard.read",
        "requires_confirmation": False,
        "secret_fields": [],
    },
    "vpn.openvpn.set_client": {
        "risk_level": "level_4_disruptive",
        "capability": "vpn.openvpn.configure",
        "requires_confirmation": True,
        "secret_fields": ["config"],
    },
    "vpn.openvpn.delete_client": {
        "risk_level": "level_3_reversible_config",
        "capability": "vpn.openvpn.configure",
        "requires_confirmation": True,
        "secret_fields": [],
    },
    "vpn.policy.set": {
        "risk_level": "level_4_disruptive",
        "capability": "vpn.policy.configure",
        "requires_confirmation": True,
        "secret_fields": [],
    },
    "vpn.policy.delete": {
        "risk_level": "level_3_reversible_config",
        "capability": "vpn.policy.configure",
        "requires_confirmation": True,
        "secret_fields": [],
    },
    "maintenance.packages.refresh": {
        "risk_level": "level_1_readonly",
        "capability": "maintenance.packages.read",
        "requires_confirmation": False,
        "secret_fields": [],
    },
    "maintenance.package.install": {
        "risk_level": "level_3_reversible_config",
        "capability": "maintenance.packages.write",
        "requires_confirmation": True,
        "secret_fields": [],
    },
    "maintenance.package.remove": {
        "risk_level": "level_3_reversible_config",
        "capability": "maintenance.packages.write",
        "requires_confirmation": True,
        "secret_fields": [],
    },
    "maintenance.backup.create": {
        "risk_level": "level_1_readonly",
        "capability": "maintenance.backup",
        "requires_confirmation": False,
        "secret_fields": [],
    },
    "maintenance.backup.restore": {
        "risk_level": "level_4_disruptive",
        "capability": "maintenance.backup",
        "requires_confirmation": True,
        "secret_fields": ["archive_base64"],
    },
    "maintenance.sysupgrade.check": {
        "risk_level": "level_2_safe_action",
        "capability": "maintenance.sysupgrade.check",
        "requires_confirmation": True,
        "secret_fields": [],
    },
    "maintenance.sysupgrade.apply": {
        "risk_level": "level_4_disruptive",
        "capability": "maintenance.sysupgrade.apply",
        "requires_confirmation": True,
        "secret_fields": [],
    },
    "maintenance.logs.read": {
        "risk_level": "level_1_readonly",
        "capability": "maintenance.logs",
        "requires_confirmation": False,
        "secret_fields": [],
    },
    "maintenance.process.signal": {
        "risk_level": "level_3_reversible_config",
        "capability": "maintenance.processes",
        "requires_confirmation": True,
        "secret_fields": [],
    },
    "maintenance.cron.set": {
        "risk_level": "level_3_reversible_config",
        "capability": "maintenance.cron",
        "requires_confirmation": True,
        "secret_fields": [],
    },
    "maintenance.diagnostics.bundle": {
        "risk_level": "level_1_readonly",
        "capability": "maintenance.diagnostics.bundle",
        "requires_confirmation": False,
        "secret_fields": [],
    },
    "maintenance.recovery.enable": {
        "risk_level": "level_3_reversible_config",
        "capability": "maintenance.recovery",
        "requires_confirmation": True,
        "secret_fields": [],
    },
    "maintenance.recovery.disable": {
        "risk_level": "level_2_safe_action",
        "capability": "maintenance.recovery",
        "requires_confirmation": True,
        "secret_fields": [],
    },
    "system.set_hostname": {
        "risk_level": "level_3_reversible_config",
        "capability": "system.set_hostname",
        "requires_confirmation": True,
        "secret_fields": [],
    },
    "system.restart_service": {
        "risk_level": "level_3_reversible_config",
        "capability": "system.restart_service",
        "requires_confirmation": True,
        "secret_fields": [],
    },
    "dhcp.set_lease": {
        "risk_level": "level_3_reversible_config",
        "capability": "dhcp.set_lease",
        "requires_confirmation": True,
        "secret_fields": [],
    },
    "dhcp.delete_lease": {
        "risk_level": "level_3_reversible_config",
        "capability": "dhcp.delete_lease",
        "requires_confirmation": True,
        "secret_fields": [],
    },
    "dhcp.set_pool": {
        "risk_level": "level_3_reversible_config",
        "capability": "dhcp.configure",
        "requires_confirmation": True,
        "secret_fields": [],
    },
    "dns.set_servers": {
        "risk_level": "level_3_reversible_config",
        "capability": "dns.configure",
        "requires_confirmation": True,
        "secret_fields": [],
    },
    "dns.install_dot": {
        "risk_level": "level_2_safe_write",
        "capability": "dns.encrypted.install",
        "requires_confirmation": True,
        "secret_fields": [],
    },
    "dns.install_doh": {
        "risk_level": "level_2_safe_write",
        "capability": "dns.encrypted.install",
        "requires_confirmation": True,
        "secret_fields": [],
    },
    "dns.set_dot": {
        "risk_level": "level_3_reversible_config",
        "capability": "dns.dot.configure",
        "requires_confirmation": True,
        "secret_fields": [],
    },
    "dns.set_doh": {
        "risk_level": "level_3_reversible_config",
        "capability": "dns.doh.configure",
        "requires_confirmation": True,
        "secret_fields": [],
    },
    "firewall.set_port_forward": {
        "risk_level": "level_4_disruptive",
        "capability": "firewall.port_forward",
        "requires_confirmation": True,
        "secret_fields": [],
    },
    "firewall.delete_port_forward": {
        "risk_level": "level_4_disruptive",
        "capability": "firewall.port_forward",
        "requires_confirmation": True,
        "secret_fields": [],
    },
    "firewall.set_zone": {
        "risk_level": "level_4_disruptive",
        "capability": "firewall.zones.configure",
        "requires_confirmation": True,
        "secret_fields": [],
    },
    "firewall.delete_zone": {
        "risk_level": "level_4_disruptive",
        "capability": "firewall.zones.configure",
        "requires_confirmation": True,
        "secret_fields": [],
    },
    "firewall.set_forwarding": {
        "risk_level": "level_4_disruptive",
        "capability": "firewall.zones.configure",
        "requires_confirmation": True,
        "secret_fields": [],
    },
    "firewall.delete_forwarding": {
        "risk_level": "level_4_disruptive",
        "capability": "firewall.zones.configure",
        "requires_confirmation": True,
        "secret_fields": [],
    },
    "firewall.set_rule": {
        "risk_level": "level_4_disruptive",
        "capability": "firewall.rules.configure",
        "requires_confirmation": True,
        "secret_fields": [],
    },
    "firewall.delete_rule": {
        "risk_level": "level_4_disruptive",
        "capability": "firewall.rules.configure",
        "requires_confirmation": True,
        "secret_fields": [],
    },
    "client.set_blocked": {
        "risk_level": "level_3_reversible_config",
        "capability": "clients.block",
        "requires_confirmation": True,
        "secret_fields": [],
    },
    "client.set_policy": {
        "risk_level": "level_3_reversible_config",
        "capability": "clients.policy",
        "requires_confirmation": True,
        "secret_fields": [],
    },
    "qos.set_sqm": {
        "risk_level": "level_3_reversible_config",
        "capability": "qos.sqm",
        "requires_confirmation": True,
        "secret_fields": [],
    },
    "wifi.set_guest": {
        "risk_level": "level_4_disruptive",
        "capability": "wifi.guest",
        "requires_confirmation": True,
        "secret_fields": ["password", "key"],
    },
    "system.set_timezone": {
        "risk_level": "level_3_reversible_config",
        "capability": "system.set_timezone",
        "requires_confirmation": True,
        "secret_fields": [],
    },
    "system.set_ntp": {
        "risk_level": "level_3_reversible_config",
        "capability": "system.set_ntp",
        "requires_confirmation": True,
        "secret_fields": [],
    },
    "diagnostics.run": {
        "risk_level": "level_1_readonly",
        "capability": "diagnostics.check_server",
        "requires_confirmation": False,
        "secret_fields": [],
    },
    "agent.disconnect": {
        "risk_level": "level_3_reversible_config",
        "capability": "agent.disable",
        "requires_confirmation": True,
        "secret_fields": [],
    },
    "agent.update": {
        "risk_level": "level_2_safe_action",
        "capability": "agent.update",
        "requires_confirmation": True,
        "secret_fields": [],
    },
    "agent.rollback": {
        "risk_level": "level_2_safe_action",
        "capability": "agent.rollback",
        "requires_confirmation": True,
        "secret_fields": [],
    },
    "agent.set_auto_update": {
        "risk_level": "level_2_safe_action",
        "capability": "agent.update",
        "requires_confirmation": True,
        "secret_fields": [],
    },
    "agent.set_interval": {
        "risk_level": "level_2_safe_action",
        "capability": "agent.set_interval",
        "requires_confirmation": True,
        "secret_fields": [],
    },
}

ALLOWED_COMMANDS = set(COMMAND_REGISTRY)


def get_command_metadata(command_type: str) -> dict[str, Any]:
    metadata = COMMAND_REGISTRY.get(command_type)
    if not metadata:
        raise HTTPException(status_code=400, detail="Command is not allowed")
    return metadata


def _require_confirmation(command_type: str, confirmed: bool) -> None:
    metadata = get_command_metadata(command_type)
    if metadata["requires_confirmation"] and not confirmed:
        raise HTTPException(
            status_code=400,
            detail=f"Command '{command_type}' requires confirmation",
        )


def _require_string(
    payload: dict[str, Any], key: str, *, min_length: int = 1, max_length: int = 255
) -> str:
    value = str(payload.get(key, "")).strip()
    if not value:
        raise HTTPException(status_code=400, detail=f"Field '{key}' is required")
    if len(value) < min_length or len(value) > max_length:
        raise HTTPException(
            status_code=400,
            detail=f"Field '{key}' must contain {min_length}..{max_length} characters",
        )
    if any(ord(char) < 32 for char in value):
        raise HTTPException(
            status_code=400,
            detail=f"Field '{key}' contains unsupported control characters",
        )
    return value


def _optional_string(payload: dict[str, Any], key: str) -> str | None:
    raw = payload.get(key)
    if raw is None:
        return None
    value = str(raw).strip()
    if not value:
        return None
    if any(ord(char) < 32 for char in value):
        raise HTTPException(
            status_code=400,
            detail=f"Field '{key}' contains unsupported control characters",
        )
    return value


def _normalize_wifi_enabled_payload(payload: dict[str, Any]) -> dict[str, Any]:
    if "enabled" not in payload or not isinstance(payload["enabled"], bool):
        raise HTTPException(
            status_code=400, detail="Field 'enabled' must be provided as boolean"
        )
    normalized = {"enabled": payload["enabled"]}
    radio = _optional_string(payload, "radio")
    if radio:
        normalized["radio"] = radio
    return normalized


def _normalize_wifi_ssid_payload(payload: dict[str, Any]) -> dict[str, Any]:
    normalized = {"ssid": _require_string(payload, "ssid", min_length=1, max_length=32)}
    iface = _optional_string(payload, "iface")
    if iface:
        normalized["iface"] = iface
    return normalized


def _normalize_wifi_password_payload(payload: dict[str, Any]) -> dict[str, Any]:
    password = _require_string(payload, "password", min_length=8, max_length=63)
    normalized = {"password": password, "key": password}
    iface = _optional_string(payload, "iface")
    if iface:
        normalized["iface"] = iface
    return normalized


def _safe_identifier(value: str, field: str, pattern: str) -> str:
    if not re.fullmatch(pattern, value):
        raise HTTPException(
            status_code=400, detail=f"Field '{field}' has invalid format"
        )
    return value


def _normalize_wifi_channel_payload(payload: dict[str, Any]) -> dict[str, Any]:
    radio = _safe_identifier(
        _require_string(payload, "radio", max_length=40),
        "radio",
        r"[A-Za-z0-9_@.\[\]-]+",
    )
    channel = _require_string(payload, "channel", max_length=4).lower()
    if channel != "auto":
        try:
            channel_number = int(channel)
        except ValueError as exc:
            raise HTTPException(
                status_code=400, detail="Invalid Wi-Fi channel"
            ) from exc
        if channel_number < 1 or channel_number > 233:
            raise HTTPException(status_code=400, detail="Invalid Wi-Fi channel")
        channel = str(channel_number)
    return {"radio": radio, "channel": channel}


def _normalize_wifi_country_payload(payload: dict[str, Any]) -> dict[str, Any]:
    radio = _safe_identifier(
        _require_string(payload, "radio", max_length=40),
        "radio",
        r"[A-Za-z0-9_@.\[\]-]+",
    )
    country = _require_string(payload, "country", min_length=2, max_length=2).upper()
    _safe_identifier(country, "country", r"[A-Z]{2}")
    return {"radio": radio, "country": country}


def _wifi_selector(payload: dict[str, Any], key: str) -> str:
    return _safe_identifier(
        _require_string(payload, key, max_length=64),
        key,
        r"[A-Za-z0-9_@.\[\]-]+",
    )


def _boolean(payload: dict[str, Any], key: str, *, default: bool | None = None) -> bool:
    value = payload.get(key, default)
    if not isinstance(value, bool):
        raise HTTPException(status_code=400, detail=f"Field '{key}' must be boolean")
    return value


def _wifi_encryption(payload: dict[str, Any], *, required: bool = True) -> str | None:
    encryption = _optional_string(payload, "encryption")
    if not encryption and not required:
        return None
    encryption = (encryption or "sae-mixed").lower()
    if encryption not in {"none", "psk2", "sae", "sae-mixed"}:
        raise HTTPException(status_code=400, detail="Unsupported Wi-Fi encryption")
    return encryption


def _wifi_key(payload: dict[str, Any], encryption: str, *, required: bool) -> str:
    if encryption == "none":
        return ""
    key = _optional_string(payload, "password") or _optional_string(payload, "key")
    if not key and not required:
        return ""
    if not key or len(key) < 8 or len(key) > 63:
        raise HTTPException(
            status_code=400, detail="Wi-Fi password must contain 8..63 characters"
        )
    if any(ord(char) < 32 for char in key):
        raise HTTPException(
            status_code=400, detail="Wi-Fi password contains control characters"
        )
    return key


def _normalize_wifi_radio_payload(payload: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {"radio": _wifi_selector(payload, "radio")}
    channel = _optional_string(payload, "channel")
    if channel:
        result.update(
            _normalize_wifi_channel_payload(
                {"radio": result["radio"], "channel": channel}
            )
        )
    country = _optional_string(payload, "country")
    if country:
        result["country"] = _normalize_wifi_country_payload(
            {"radio": result["radio"], "country": country}
        )["country"]
    htmode = _optional_string(payload, "htmode")
    if htmode:
        result["htmode"] = _safe_identifier(
            htmode.upper(),
            "htmode",
            r"(?:NOHT|HT(?:20|40[+-]?)|VHT(?:20|40|80|160)|HE(?:20|40|80|160))",
        )
    txpower = _integer(payload, "txpower", 1, 40, required=False)
    if txpower is not None:
        result["txpower"] = txpower
    if len(result) == 1:
        raise HTTPException(
            status_code=400, detail="At least one radio setting is required"
        )
    return result


def _normalize_wifi_add_ssid_payload(payload: dict[str, Any]) -> dict[str, Any]:
    encryption = _wifi_encryption(payload) or "sae-mixed"
    return {
        "radio": _wifi_selector(payload, "radio"),
        "ssid": _require_string(payload, "ssid", max_length=32),
        "network": _safe_identifier(
            str(payload.get("network") or "lan"), "network", r"[A-Za-z0-9_.-]+"
        ),
        "encryption": encryption,
        "key": _wifi_key(payload, encryption, required=encryption != "none"),
        "hidden": _boolean(payload, "hidden", default=False),
        "isolate": _boolean(payload, "isolate", default=False),
    }


def _normalize_wifi_update_ssid_payload(payload: dict[str, Any]) -> dict[str, Any]:
    encryption = _wifi_encryption(payload) or "sae-mixed"
    result = {
        "iface": _wifi_selector(payload, "iface"),
        "ssid": _require_string(payload, "ssid", max_length=32),
        "network": _safe_identifier(
            str(payload.get("network") or "lan"), "network", r"[A-Za-z0-9_.-]+"
        ),
        "encryption": encryption,
        "enabled": _boolean(payload, "enabled", default=True),
        "hidden": _boolean(payload, "hidden", default=False),
        "isolate": _boolean(payload, "isolate", default=False),
        "ieee80211r": _boolean(payload, "ieee80211r", default=False),
        "ieee80211k": _boolean(payload, "ieee80211k", default=False),
        "bss_transition": _boolean(payload, "bss_transition", default=False),
    }
    key = _wifi_key(payload, encryption, required=False)
    if key or encryption == "none":
        result["key"] = key
    mobility_domain = _optional_string(payload, "mobility_domain")
    if result["ieee80211r"]:
        result["mobility_domain"] = _safe_identifier(
            mobility_domain or "4f57", "mobility_domain", r"[0-9A-Fa-f]{4}"
        ).lower()
    return result


def _normalize_wifi_schedule_payload(payload: dict[str, Any]) -> dict[str, Any]:
    enabled = _boolean(payload, "enabled")
    weekdays = _string_list(payload, "weekdays")
    allowed = {"mon", "tue", "wed", "thu", "fri", "sat", "sun"}
    weekdays = [day.lower() for day in weekdays]
    if any(day not in allowed for day in weekdays):
        raise HTTPException(status_code=400, detail="Invalid Wi-Fi schedule weekday")
    start = str(payload.get("start") or "")
    stop = str(payload.get("stop") or "")
    if enabled:
        if not weekdays:
            raise HTTPException(
                status_code=400, detail="Wi-Fi schedule weekdays are required"
            )
        for field, value in (("start", start), ("stop", stop)):
            if not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", value):
                raise HTTPException(
                    status_code=400, detail=f"Invalid Wi-Fi schedule {field}"
                )
        if start == stop:
            raise HTTPException(
                status_code=400, detail="Wi-Fi schedule start and stop must differ"
            )
    return {
        "radio": _wifi_selector(payload, "radio"),
        "enabled": enabled,
        "weekdays": weekdays,
        "start": start,
        "stop": stop,
    }


def _normalize_wifi_mesh_payload(payload: dict[str, Any]) -> dict[str, Any]:
    enabled = _boolean(payload, "enabled")
    result: dict[str, Any] = {
        "radio": _wifi_selector(payload, "radio"),
        "enabled": enabled,
    }
    if enabled:
        encryption = str(payload.get("encryption") or "sae").lower()
        if encryption not in {"none", "sae"}:
            raise HTTPException(
                status_code=400, detail="Mesh encryption must be none or sae"
            )
        result.update(
            mesh_id=_require_string(payload, "mesh_id", max_length=32),
            network=_safe_identifier(
                str(payload.get("network") or "lan"), "network", r"[A-Za-z0-9_.-]+"
            ),
            encryption=encryption,
            key=_wifi_key(payload, encryption, required=encryption != "none"),
        )
    return result


def _normalize_interface_payload(payload: dict[str, Any]) -> dict[str, Any]:
    interface = _require_string(payload, "interface", max_length=32)
    return {"interface": _safe_identifier(interface, "interface", r"[A-Za-z0-9_.-]+")}


def _normalize_hostname_payload(payload: dict[str, Any]) -> dict[str, Any]:
    hostname = _require_string(payload, "hostname", max_length=63)
    return {
        "hostname": _safe_identifier(
            hostname, "hostname", r"[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?"
        )
    }


def _normalize_service_payload(payload: dict[str, Any]) -> dict[str, Any]:
    service = _require_string(payload, "service", max_length=32)
    if service not in {"network", "dnsmasq", "firewall", "odhcpd"}:
        raise HTTPException(status_code=400, detail="Service is not allowed")
    return {"service": service}


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


def _ipv4(payload: dict[str, Any], key: str, *, required: bool = True) -> str | None:
    value = _optional_string(payload, key)
    if not value:
        if required:
            raise HTTPException(status_code=400, detail=f"Field '{key}' is required")
        return None
    try:
        return str(IPv4Address(value))
    except AddressValueError as exc:
        raise HTTPException(
            status_code=400, detail=f"Field '{key}' is not a valid IPv4 address"
        ) from exc


def _integer(
    payload: dict[str, Any],
    key: str,
    minimum: int,
    maximum: int,
    *,
    required: bool = True,
) -> int | None:
    value = payload.get(key)
    if value in (None, ""):
        if required:
            raise HTTPException(status_code=400, detail=f"Field '{key}' is required")
        return None
    try:
        result = int(str(value).strip())
    except (TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=400, detail=f"Field '{key}' must be an integer"
        ) from exc
    if result < minimum or result > maximum:
        raise HTTPException(
            status_code=400,
            detail=f"Field '{key}' must be between {minimum} and {maximum}",
        )
    return result


def _string_list(
    payload: dict[str, Any], key: str, *, required: bool = False
) -> list[str]:
    raw = payload.get(key, [])
    values = raw if isinstance(raw, list) else re.split(r"[\s,;]+", str(raw).strip())
    result = [str(value).strip() for value in values if str(value).strip()]
    if required and not result:
        raise HTTPException(status_code=400, detail=f"Field '{key}' is required")
    if len(result) > 8:
        raise HTTPException(
            status_code=400, detail=f"Field '{key}' contains too many values"
        )
    return result


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


def _normalize_port_forward_payload(
    payload: dict[str, Any], *, delete: bool = False
) -> dict[str, Any]:
    name = _safe_identifier(
        _require_string(payload, "name", max_length=40), "name", r"[A-Za-z0-9_.-]+"
    )
    if delete:
        return {"name": name}
    protocol = str(payload.get("protocol") or "tcp").lower()
    if protocol not in {"tcp", "udp", "tcpudp"}:
        raise HTTPException(
            status_code=400, detail="Protocol must be tcp, udp or tcpudp"
        )
    return {
        "name": name,
        "protocol": protocol,
        "external_port": _integer(payload, "external_port", 1, 65535),
        "internal_ip": _ipv4(payload, "internal_ip"),
        "internal_port": _integer(payload, "internal_port", 1, 65535),
    }


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


def _normalize_guest_payload(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload.get("enabled"), bool):
        raise HTTPException(
            status_code=400, detail="Field 'enabled' must be provided as boolean"
        )
    result: dict[str, Any] = {"enabled": payload["enabled"]}
    if payload["enabled"]:
        result["ssid"] = _require_string(payload, "ssid", max_length=32)
        result["password"] = _require_string(
            payload, "password", min_length=8, max_length=63
        )
    radio = _optional_string(payload, "radio")
    if radio:
        result["radio"] = _safe_identifier(radio, "radio", r"[A-Za-z0-9_.@\[\]-]+")
    return result


def _normalize_timezone_payload(payload: dict[str, Any]) -> dict[str, Any]:
    zonename = _safe_identifier(
        _require_string(payload, "zonename", max_length=64),
        "zonename",
        r"[A-Za-z0-9_+./-]+",
    )
    timezone = _safe_identifier(
        _optional_string(payload, "timezone") or TIMEZONE_BY_NAME.get(zonename, ""),
        "timezone",
        r"[A-Za-z0-9_+,:./<>-]+",
    )
    return {"zonename": zonename, "timezone": timezone}


def _normalize_ntp_payload(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload.get("enabled"), bool):
        raise HTTPException(
            status_code=400, detail="Field 'enabled' must be provided as boolean"
        )
    servers = _string_list(payload, "servers", required=payload["enabled"])
    for server in servers:
        _safe_identifier(server, "servers", r"[A-Za-z0-9_.:-]+")
    return {"enabled": payload["enabled"], "servers": servers}


def _name(payload: dict[str, Any], key: str = "name") -> str:
    return _safe_identifier(
        _require_string(payload, key, max_length=64), key, r"[A-Za-z0-9_.-]+"
    )


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


def _normalize_multiwan_payload(payload: dict[str, Any]) -> dict[str, Any]:
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


def _normalize_zone_payload(payload: dict[str, Any]) -> dict[str, Any]:
    def policy(key: str) -> str:
        return _safe_identifier(
            str(payload.get(key) or "REJECT").upper(),
            key,
            r"(?:ACCEPT|REJECT|DROP)",
        )

    return {
        "section": _uci_section(payload),
        "name": _name(payload),
        "networks": [
            _safe_identifier(v, "networks", r"[A-Za-z0-9_.-]+")
            for v in _string_list(payload, "networks", required=True)
        ],
        "input": policy("input"),
        "output": policy("output"),
        "forward": policy("forward"),
        "masquerade": _boolean(payload, "masquerade", default=False),
    }


def _normalize_forwarding_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "section": _uci_section(payload),
        "src": _name(payload, "src"),
        "dest": _name(payload, "dest"),
        "enabled": _boolean(payload, "enabled"),
    }


def _normalize_firewall_rule_payload(payload: dict[str, Any]) -> dict[str, Any]:
    protocol = str(payload.get("protocol") or "tcpudp").lower()
    if protocol not in {"tcp", "udp", "tcpudp", "icmp", "all"}:
        raise HTTPException(status_code=400, detail="Invalid firewall protocol")
    target = str(payload.get("target") or "ACCEPT").upper()
    if target not in {"ACCEPT", "REJECT", "DROP"}:
        raise HTTPException(status_code=400, detail="Invalid firewall target")
    return {
        "section": _uci_section(payload),
        "name": _name(payload),
        "src": _optional_string(payload, "src") or "*",
        "dest": _optional_string(payload, "dest") or "*",
        "protocol": protocol,
        "src_ip": _optional_string(payload, "src_ip") or "",
        "dest_ip": _optional_string(payload, "dest_ip") or "",
        "src_port": _optional_string(payload, "src_port") or "",
        "dest_port": _optional_string(payload, "dest_port") or "",
        "target": target,
    }


def _uci_section(payload: dict[str, Any]) -> str:
    section = _optional_string(payload, "section") or ""
    if section and not re.fullmatch(
        r"(?:@[A-Za-z0-9_-]+\[[0-9]+\]|[A-Za-z0-9_.-]+)", section
    ):
        raise HTTPException(status_code=400, detail="Invalid UCI section")
    return section


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


def _maintenance_package(
    payload: dict[str, Any], *, remove: bool = False
) -> dict[str, str]:
    package = _require_string(payload, "package", max_length=128)
    if not re.fullmatch(r"[A-Za-z0-9+_.-]+", package):
        raise HTTPException(status_code=400, detail="Invalid package name")
    if remove and package in {
        "base-files",
        "busybox",
        "dnsmasq",
        "dropbear",
        "firewall4",
        "kernel",
        "libc",
        "netifd",
        "procd",
        "ubus",
        "uci",
        "wrtmonitor",
        "wrtmonitor-agent",
    }:
        raise HTTPException(
            status_code=400, detail="system package removal is not allowed"
        )
    return {"package": package}


def _maintenance_backup_restore(payload: dict[str, Any]) -> dict[str, str]:
    archive = _require_string(payload, "archive_base64", max_length=2_000_000)
    try:
        decoded = base64.b64decode(archive, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise HTTPException(status_code=400, detail="Invalid backup archive") from exc
    if not decoded.startswith(b"\x1f\x8b") or len(decoded) > 1_500_000:
        raise HTTPException(status_code=400, detail="Invalid backup archive")
    return {"archive_base64": archive}


def _maintenance_sysupgrade(payload: dict[str, Any], *, apply: bool) -> dict[str, Any]:
    checksum = _require_string(payload, "sha256", max_length=64).lower()
    if not re.fullmatch(r"[0-9a-f]{64}", checksum):
        raise HTTPException(status_code=400, detail="Invalid firmware checksum")
    result: dict[str, Any] = {
        "sha256": checksum,
        "preserve_config": _boolean(payload, "preserve_config", default=True),
    }
    if not apply:
        url = _require_string(payload, "url", max_length=2048)
        parsed = urlsplit(url)
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.username
            or parsed.password
        ):
            raise HTTPException(status_code=400, detail="Firmware URL must use HTTPS")
        result["url"] = url
        result["expected_model"] = _optional_string(payload, "expected_model") or ""
    return result


def _maintenance_cron(payload: dict[str, Any]) -> dict[str, str]:
    content = str(payload.get("content") or "")
    if len(content) > 8192 or any(
        ord(char) < 32 and char not in "\r\n\t" for char in content
    ):
        raise HTTPException(status_code=400, detail="Invalid cron content")
    if any(
        line.lstrip().startswith(("@reboot", "@hourly", "@daily"))
        for line in content.splitlines()
    ):
        raise HTTPException(status_code=400, detail="Cron macros are not supported")
    return {"content": content.rstrip() + ("\n" if content else "")}


def _normalize_diagnostics_payload(payload: dict[str, Any]) -> dict[str, Any]:
    checks = payload.get("checks")
    if checks in (None, [], ()):
        return {"checks": sorted(ALLOWED_DIAGNOSTIC_CHECKS)}
    if not isinstance(checks, list):
        raise HTTPException(status_code=400, detail="Field 'checks' must be a list")
    invalid = sorted(
        {str(item) for item in checks if str(item) not in ALLOWED_DIAGNOSTIC_CHECKS}
    )
    if invalid:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported diagnostics checks: {', '.join(invalid)}",
        )
    normalized_checks: list[str] = []
    for item in checks:
        value = str(item)
        if value not in normalized_checks:
            normalized_checks.append(value)
    return {"checks": normalized_checks}


def _normalize_auto_update_payload(payload: dict[str, Any]) -> dict[str, Any]:
    if "enabled" not in payload or not isinstance(payload["enabled"], bool):
        raise HTTPException(
            status_code=400, detail="Field 'enabled' must be provided as boolean"
        )
    return {"enabled": payload["enabled"]}


def _normalize_interval_payload(payload: dict[str, Any]) -> dict[str, Any]:
    value = payload.get("interval_seconds")
    if value is None or isinstance(value, bool):
        raise HTTPException(
            status_code=400,
            detail="Field 'interval_seconds' must be an integer not less than 5",
        )
    try:
        normalized = int(str(value).strip())
    except (TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=400,
            detail="Field 'interval_seconds' must be an integer not less than 5",
        ) from exc
    if normalized < 5:
        raise HTTPException(
            status_code=400,
            detail="Field 'interval_seconds' must be an integer not less than 5",
        )
    return {"interval_seconds": normalized}


def validate_command_payload(
    command_type: str, payload: dict[str, Any]
) -> dict[str, Any]:
    normalized_payload = dict(payload or {})
    if command_type == "wifi.set_enabled":
        return _normalize_wifi_enabled_payload(normalized_payload)
    if command_type == "wifi.set_ssid":
        return _normalize_wifi_ssid_payload(normalized_payload)
    if command_type == "wifi.set_password":
        return _normalize_wifi_password_payload(normalized_payload)
    if command_type == "wifi.set_channel":
        return _normalize_wifi_channel_payload(normalized_payload)
    if command_type == "wifi.set_country":
        return _normalize_wifi_country_payload(normalized_payload)
    if command_type == "wifi.set_radio":
        return _normalize_wifi_radio_payload(normalized_payload)
    if command_type == "wifi.add_ssid":
        return _normalize_wifi_add_ssid_payload(normalized_payload)
    if command_type == "wifi.update_ssid":
        return _normalize_wifi_update_ssid_payload(normalized_payload)
    if command_type == "wifi.delete_ssid":
        return {"iface": _wifi_selector(normalized_payload, "iface")}
    if command_type == "wifi.set_schedule":
        return _normalize_wifi_schedule_payload(normalized_payload)
    if command_type == "wifi.set_mesh":
        return _normalize_wifi_mesh_payload(normalized_payload)
    if command_type == "network.interface_restart":
        return _normalize_interface_payload(normalized_payload)
    if command_type == "network.set_wan":
        return _normalize_wan_payload(normalized_payload)
    if command_type == "network.set_lan":
        return _normalize_lan_payload(normalized_payload)
    if command_type == "network.set_ipv6":
        return _normalize_ipv6_payload(normalized_payload)
    if command_type == "network.set_multiwan":
        return _normalize_multiwan_payload(normalized_payload)
    if command_type == "network.set_route":
        return _normalize_route_payload(normalized_payload)
    if command_type == "network.delete_route":
        return {"name": _name(normalized_payload)}
    if command_type == "network.set_ddns":
        return _normalize_ddns_payload(normalized_payload)
    if command_type == "network.set_upnp":
        return {
            "enabled": _boolean(normalized_payload, "enabled"),
            "secure_mode": _boolean(normalized_payload, "secure_mode", default=True),
        }
    if command_type == "vpn.wireguard.set_interface":
        return _normalize_wireguard_interface_payload(normalized_payload)
    if command_type == "vpn.wireguard.set_peer":
        return _normalize_wireguard_peer_payload(normalized_payload)
    if command_type in {"vpn.wireguard.delete_peer", "vpn.wireguard.export_peer"}:
        return {
            "interface": _safe_identifier(
                _require_string(normalized_payload, "interface", max_length=32),
                "interface",
                r"[A-Za-z0-9_.-]+",
            ),
            "name": _name(normalized_payload),
        }
    if command_type == "vpn.openvpn.set_client":
        return _normalize_openvpn_payload(normalized_payload)
    if command_type == "vpn.openvpn.delete_client":
        return {"name": _name(normalized_payload)}
    if command_type == "vpn.policy.set":
        return _normalize_vpn_policy_payload(normalized_payload)
    if command_type == "vpn.policy.delete":
        return {"name": _name(normalized_payload)}
    if command_type in {
        "maintenance.packages.refresh",
        "maintenance.backup.create",
        "maintenance.diagnostics.bundle",
        "maintenance.recovery.enable",
        "maintenance.recovery.disable",
    }:
        return {}
    if command_type == "maintenance.package.install":
        return _maintenance_package(normalized_payload)
    if command_type == "maintenance.package.remove":
        return _maintenance_package(normalized_payload, remove=True)
    if command_type == "maintenance.backup.restore":
        return _maintenance_backup_restore(normalized_payload)
    if command_type == "maintenance.sysupgrade.check":
        return _maintenance_sysupgrade(normalized_payload, apply=False)
    if command_type == "maintenance.sysupgrade.apply":
        return _maintenance_sysupgrade(normalized_payload, apply=True)
    if command_type == "maintenance.logs.read":
        return {"lines": _integer(normalized_payload, "lines", 20, 500) or 100}
    if command_type == "maintenance.process.signal":
        return {
            "pid": _integer(normalized_payload, "pid", 2, 4_194_304),
            "signal": _safe_identifier(
                str(normalized_payload.get("signal") or "TERM"),
                "signal",
                r"(?:TERM|HUP|KILL)",
            ),
        }
    if command_type == "maintenance.cron.set":
        return _maintenance_cron(normalized_payload)
    if command_type == "firewall.set_zone":
        return _normalize_zone_payload(normalized_payload)
    if command_type == "firewall.delete_zone":
        zone = {
            "section": _uci_section(normalized_payload),
            "name": _name(normalized_payload),
        }
        if zone["name"] in {"lan", "wan"}:
            raise HTTPException(
                status_code=400, detail="core firewall zone cannot be deleted"
            )
        return zone
    if command_type == "firewall.set_forwarding":
        return _normalize_forwarding_payload(normalized_payload)
    if command_type == "firewall.delete_forwarding":
        return {
            "section": _uci_section(normalized_payload),
            "src": _name(normalized_payload, "src"),
            "dest": _name(normalized_payload, "dest"),
        }
    if command_type == "firewall.set_rule":
        return _normalize_firewall_rule_payload(normalized_payload)
    if command_type == "firewall.delete_rule":
        return {
            "section": _uci_section(normalized_payload),
            "name": _name(normalized_payload),
        }
    if command_type == "system.set_hostname":
        return _normalize_hostname_payload(normalized_payload)
    if command_type == "system.restart_service":
        return _normalize_service_payload(normalized_payload)
    if command_type == "dhcp.set_lease":
        return _normalize_dhcp_lease_payload(normalized_payload)
    if command_type == "dhcp.delete_lease":
        return _normalize_dhcp_lease_payload(normalized_payload, delete=True)
    if command_type == "dhcp.set_pool":
        return _normalize_dhcp_pool_payload(normalized_payload)
    if command_type == "dns.set_servers":
        return _normalize_dns_payload(normalized_payload)
    if command_type in {"dns.install_dot", "dns.install_doh"}:
        return {"mode": command_type.rsplit("_", 1)[1]}
    if command_type in {"dns.set_dot", "dns.set_doh"}:
        provider = str(normalized_payload.get("provider") or "cloudflare").strip()
        if provider not in {"cloudflare", "quad9", "google"}:
            raise HTTPException(status_code=400, detail="Unsupported DNS provider")
        return {
            "mode": command_type.rsplit("_", 1)[1],
            "provider": provider,
            "enabled": _boolean(normalized_payload, "enabled", default=True),
        }
    if command_type == "firewall.set_port_forward":
        return _normalize_port_forward_payload(normalized_payload)
    if command_type == "firewall.delete_port_forward":
        return _normalize_port_forward_payload(normalized_payload, delete=True)
    if command_type == "client.set_blocked":
        return _normalize_client_block_payload(normalized_payload)
    if command_type == "client.set_policy":
        return _normalize_client_policy_payload(normalized_payload)
    if command_type == "qos.set_sqm":
        return _normalize_sqm_payload(normalized_payload)
    if command_type == "wifi.set_guest":
        return _normalize_guest_payload(normalized_payload)
    if command_type == "system.set_timezone":
        return _normalize_timezone_payload(normalized_payload)
    if command_type == "system.set_ntp":
        return _normalize_ntp_payload(normalized_payload)
    if command_type == "diagnostics.run":
        return _normalize_diagnostics_payload(normalized_payload)
    if command_type == "agent.set_auto_update":
        return _normalize_auto_update_payload(normalized_payload)
    if command_type == "agent.set_interval":
        return _normalize_interval_payload(normalized_payload)
    return normalized_payload


def build_command_payload_from_web_form(
    command_type: str,
    *,
    ssid: str = "",
    enabled: str = "true",
    wifi_password: str = "",
    channel: str = "",
    country: str = "",
    interval_seconds: str = "",
    radio: str = "",
    iface: str = "",
    interface: str = "",
    hostname: str = "",
    service: str = "",
    mac: str = "",
    ip: str = "",
    diagnostics_checks: list[str] | None = None,
    protocol: str = "",
    ip_address: str = "",
    netmask: str = "",
    gateway: str = "",
    dns: str = "",
    username: str = "",
    password: str = "",
    mtu: str = "",
    start: str = "",
    limit: str = "",
    leasetime: str = "",
    servers: str = "",
    name: str = "",
    external_port: str = "",
    internal_ip: str = "",
    internal_port: str = "",
    blocked: str = "true",
    zonename: str = "",
    timezone: str = "",
    download_kbps: str = "",
    upload_kbps: str = "",
    htmode: str = "",
    txpower: str = "",
    network: str = "",
    encryption: str = "",
    hidden: str = "false",
    isolate: str = "false",
    ieee80211r: str = "false",
    ieee80211k: str = "false",
    bss_transition: str = "false",
    mobility_domain: str = "",
    weekdays: list[str] | None = None,
    stop: str = "",
    mesh_id: str = "",
    public_key: str = "",
    preshared_key: str = "",
    allowed_ips: str = "",
    endpoint: str = "",
    config_text: str = "",
    source: str = "",
    destination: str = "",
    url: str = "",
    sha256: str = "",
    archive_base64: str = "",
    content: str = "",
    pid: str = "",
    signal: str = "",
    uci_section: str = "",
) -> dict[str, Any]:
    if command_type not in ALLOWED_COMMANDS:
        raise ValueError("Unsupported command")
    payload: dict[str, Any] = {}
    if command_type == "wifi.set_ssid":
        payload = {"ssid": ssid, "iface": iface}
    elif command_type == "wifi.set_enabled":
        payload = {"enabled": enabled.lower() == "true", "radio": radio}
    elif command_type == "wifi.set_password":
        payload = {"password": wifi_password, "iface": iface}
    elif command_type == "wifi.set_channel":
        payload = {"channel": channel, "radio": radio}
    elif command_type == "wifi.set_country":
        payload = {"country": country, "radio": radio}
    elif command_type == "wifi.set_radio":
        payload = {
            "radio": radio,
            "channel": channel,
            "country": country,
            "htmode": htmode,
            "txpower": txpower,
        }
    elif command_type == "wifi.add_ssid":
        payload = {
            "radio": radio,
            "ssid": ssid,
            "network": network or "lan",
            "encryption": encryption or "sae-mixed",
            "key": wifi_password,
            "hidden": hidden.lower() == "true",
            "isolate": isolate.lower() == "true",
        }
    elif command_type == "wifi.update_ssid":
        payload = {
            "iface": iface,
            "ssid": ssid,
            "network": network or "lan",
            "encryption": encryption or "sae-mixed",
            "key": wifi_password,
            "enabled": enabled.lower() == "true",
            "hidden": hidden.lower() == "true",
            "isolate": isolate.lower() == "true",
            "ieee80211r": ieee80211r.lower() == "true",
            "ieee80211k": ieee80211k.lower() == "true",
            "bss_transition": bss_transition.lower() == "true",
            "mobility_domain": mobility_domain,
        }
    elif command_type == "wifi.delete_ssid":
        payload = {"iface": iface}
    elif command_type == "wifi.set_schedule":
        payload = {
            "radio": radio,
            "enabled": enabled.lower() == "true",
            "weekdays": weekdays or [],
            "start": start,
            "stop": stop,
        }
    elif command_type == "wifi.set_mesh":
        payload = {
            "radio": radio,
            "enabled": enabled.lower() == "true",
            "mesh_id": mesh_id,
            "network": network or "lan",
            "encryption": encryption or "sae",
            "key": wifi_password,
        }
    elif command_type == "network.interface_restart":
        payload = {"interface": interface}
    elif command_type == "network.set_wan":
        payload = {
            "interface": interface or "wan",
            "protocol": protocol,
            "ip_address": ip_address,
            "netmask": netmask,
            "gateway": gateway,
            "dns": dns,
            "username": username,
            "password": password,
            "mtu": mtu,
        }
    elif command_type == "network.set_lan":
        payload = {
            "interface": interface or "lan",
            "ip_address": ip_address,
            "netmask": netmask,
        }
    elif command_type == "network.set_ipv6":
        payload = {
            "interface": interface or "lan",
            "enabled": enabled.lower() == "true",
            "assignment_length": limit,
            "ra": protocol or "server",
            "dhcpv6": gateway or "server",
            "ndp": dns or "server",
        }
    elif command_type == "network.set_multiwan":
        payload = {
            "enabled": enabled.lower() == "true",
            "primary_interface": interface or "wan",
            "secondary_interface": name,
            "primary_metric": external_port or "10",
            "secondary_metric": internal_port or "20",
        }
    elif command_type == "network.set_route":
        payload = {
            "name": name,
            "interface": interface or "wan",
            "target": ip_address,
            "gateway": gateway,
            "metric": mtu or "0",
        }
    elif command_type == "network.delete_route":
        payload = {"name": name}
    elif command_type == "network.set_ddns":
        payload = {
            "name": name,
            "enabled": enabled.lower() == "true",
            "provider": protocol,
            "domain": hostname,
            "username": username,
            "password": password,
            "interface": interface or "wan",
        }
    elif command_type == "network.set_upnp":
        payload = {
            "enabled": enabled.lower() == "true",
            "secure_mode": blocked.lower() == "true",
        }
    elif command_type == "firewall.set_zone":
        payload = {
            "section": uci_section,
            "name": name,
            "networks": network,
            "input": protocol,
            "output": username,
            "forward": password,
            "masquerade": enabled.lower() == "true",
        }
    elif command_type == "firewall.delete_zone":
        payload = {"section": uci_section, "name": name}
    elif command_type == "firewall.set_forwarding":
        payload = {
            "section": uci_section,
            "src": interface or name,
            "dest": network,
            "enabled": enabled.lower() == "true",
        }
    elif command_type == "firewall.delete_forwarding":
        payload = {"section": uci_section, "src": interface or name, "dest": network}
    elif command_type == "firewall.set_rule":
        payload = {
            "section": uci_section,
            "name": name,
            "src": interface,
            "dest": network,
            "protocol": protocol,
            "src_ip": ip_address,
            "dest_ip": internal_ip,
            "src_port": external_port,
            "dest_port": internal_port,
            "target": hostname,
        }
    elif command_type == "firewall.delete_rule":
        payload = {"section": uci_section, "name": name}
    elif command_type == "vpn.wireguard.set_interface":
        payload = {
            "name": name or interface,
            "enabled": enabled.lower() == "true",
            "mode": protocol or "server",
            "addresses": ip_address,
            "listen_port": external_port or "51820",
            "private_key": password,
            "mtu": mtu or "1420",
        }
    elif command_type == "vpn.wireguard.set_peer":
        payload = {
            "interface": interface,
            "name": name,
            "public_key": public_key or username,
            "preshared_key": preshared_key or password,
            "allowed_ips": allowed_ips or ip_address,
            "endpoint": endpoint or hostname,
            "persistent_keepalive": internal_port or "0",
            "route_allowed_ips": enabled.lower() == "true",
        }
    elif command_type in {"vpn.wireguard.delete_peer", "vpn.wireguard.export_peer"}:
        payload = {"interface": interface, "name": name}
    elif command_type == "vpn.openvpn.set_client":
        payload = {
            "name": name,
            "enabled": enabled.lower() == "true",
            "config": config_text or protocol,
        }
    elif command_type == "vpn.openvpn.delete_client":
        payload = {"name": name}
    elif command_type == "vpn.policy.set":
        payload = {
            "name": name,
            "enabled": enabled.lower() == "true",
            "interface": interface,
            "source": source or ip_address or mac,
            "destination": destination or network,
            "protocol": protocol or "all",
        }
    elif command_type == "vpn.policy.delete":
        payload = {"name": name}
    elif command_type in {"maintenance.package.install", "maintenance.package.remove"}:
        payload = {"package": name}
    elif command_type == "maintenance.backup.restore":
        payload = {"archive_base64": archive_base64 or config_text}
    elif command_type == "maintenance.sysupgrade.check":
        payload = {
            "url": url or hostname,
            "sha256": sha256 or password,
            "expected_model": name,
            "preserve_config": enabled.lower() == "true",
        }
    elif command_type == "maintenance.sysupgrade.apply":
        payload = {
            "sha256": sha256 or password,
            "preserve_config": enabled.lower() == "true",
        }
    elif command_type == "maintenance.logs.read":
        payload = {"lines": limit or "100"}
    elif command_type == "maintenance.process.signal":
        payload = {"pid": pid or internal_port, "signal": signal or protocol or "TERM"}
    elif command_type == "maintenance.cron.set":
        payload = {"content": content or config_text}
    elif command_type in {
        "maintenance.packages.refresh",
        "maintenance.backup.create",
        "maintenance.diagnostics.bundle",
        "maintenance.recovery.enable",
        "maintenance.recovery.disable",
    }:
        payload = {}
    elif command_type == "system.set_hostname":
        payload = {"hostname": hostname}
    elif command_type == "system.restart_service":
        payload = {"service": service}
    elif command_type == "dhcp.set_lease":
        payload = {"mac": mac, "ip": ip, "hostname": hostname}
    elif command_type == "dhcp.delete_lease":
        payload = {"mac": mac}
    elif command_type == "dhcp.set_pool":
        payload = {
            "interface": interface or "lan",
            "start": start,
            "limit": limit,
            "leasetime": leasetime,
        }
    elif command_type == "dns.set_servers":
        payload = {"servers": servers}
    elif command_type in {"dns.install_dot", "dns.install_doh"}:
        payload = {"mode": command_type.rsplit("_", 1)[1]}
    elif command_type in {"dns.set_dot", "dns.set_doh"}:
        payload = {
            "mode": command_type.rsplit("_", 1)[1],
            "provider": name or "cloudflare",
            "enabled": enabled.lower() == "true",
        }
    elif command_type == "firewall.set_port_forward":
        payload = {
            "name": name,
            "protocol": protocol,
            "external_port": external_port,
            "internal_ip": internal_ip,
            "internal_port": internal_port,
        }
    elif command_type == "firewall.delete_port_forward":
        payload = {"name": name}
    elif command_type == "client.set_blocked":
        payload = {"mac": mac, "blocked": blocked.lower() == "true"}
    elif command_type == "qos.set_sqm":
        payload = {
            "enabled": enabled.lower() == "true",
            "interface": interface,
            "download_kbps": download_kbps,
            "upload_kbps": upload_kbps,
        }
    elif command_type == "wifi.set_guest":
        payload = {
            "enabled": enabled.lower() == "true",
            "ssid": ssid,
            "password": wifi_password,
            "radio": radio,
        }
    elif command_type == "system.set_timezone":
        payload = {"zonename": zonename, "timezone": timezone}
    elif command_type == "system.set_ntp":
        payload = {"enabled": enabled.lower() == "true", "servers": servers}
    elif command_type == "agent.set_auto_update":
        payload = {"enabled": enabled.lower() == "true"}
    elif command_type == "agent.set_interval":
        payload = {"interval_seconds": interval_seconds}
    elif command_type == "diagnostics.run":
        payload = {"checks": diagnostics_checks or []}
    try:
        return validate_command_payload(command_type, payload)
    except HTTPException as exc:
        raise ValueError(str(exc.detail)) from exc


def mask_secrets(value: Any, secret_fields: set[str]) -> Any:
    if isinstance(value, dict):
        return {
            key: (
                "********"
                if key in secret_fields
                else mask_secrets(item, secret_fields)
            )
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [mask_secrets(item, secret_fields) for item in value]
    return value


def public_command_payload(command_type: str, payload: dict | None) -> dict:
    metadata = COMMAND_REGISTRY.get(command_type, {})
    secret_fields = set(metadata.get("secret_fields", []))
    safe_payload = dict(payload or {})
    return mask_secrets(safe_payload, secret_fields)


def public_command_result(
    command_type: str, result: dict[str, Any] | None
) -> dict[str, Any] | None:
    if result is None:
        return None
    metadata = COMMAND_REGISTRY.get(command_type, {})
    secret_fields = set(metadata.get("secret_fields", []))
    safe_result = mask_secrets(result, secret_fields)
    for field in ("archive_base64", "bundle_base64"):
        if field in safe_result:
            safe_result[field] = "download available"
    return safe_result


def command_history_entry(command: DeviceCommand) -> dict[str, Any]:
    metadata = COMMAND_REGISTRY.get(command.command_type, {})

    def iso(value: datetime | None) -> str | None:
        return value.isoformat() if value else None

    return {
        "id": str(command.id),
        "command_type": command.command_type,
        "status": command.status,
        "source": command.source,
        "payload": public_command_payload(command.command_type, command.payload),
        "result": public_command_result(command.command_type, command.result),
        "created_at": iso(command.created_at),
        "picked_at": iso(command.picked_at),
        "completed_at": iso(command.completed_at),
        "expires_at": iso(command.expires_at),
        "retry_count": command.retry_count,
        "last_error": command.last_error,
        "risk_level": metadata.get("risk_level"),
        "capability": metadata.get("capability"),
    }


def now_utc() -> datetime:
    return datetime.now(UTC)


def create_device_command(
    db: Session,
    *,
    device_id: UUID,
    command_type: str,
    payload: dict[str, Any],
    created_by: UUID | None,
    source: str,
) -> DeviceCommand:
    now = now_utc()
    command_id = uuid4()
    if command_type == "agent.update":
        latest = db.scalars(
            select(DeviceTelemetry)
            .where(DeviceTelemetry.device_id == device_id)
            .order_by(DeviceTelemetry.created_at.desc())
            .limit(1)
        ).first()
        installed = (
            str(((latest.payload.get("agent") or {}).get("version") or ""))
            if latest
            else ""
        )
        if installed == "0.9.0":
            payload = {**payload, "allow_downgrade": True}
    command = DeviceCommand(
        id=command_id,
        device_id=device_id,
        command_type=command_type,
        payload=attach_transaction_metadata(command_type, payload, command_id),
        status="queued",
        result=None,
        created_by=created_by,
        created_at=now,
        updated_at=now,
        expires_at=now + COMMAND_TTL,
        retry_count=0,
        source=source,
    )
    db.add(command)
    return command


def validate_command_request(
    *,
    command_type: str,
    payload: dict[str, Any] | None,
    confirmed: bool,
    device_supports: Callable[[str], bool] | None = None,
) -> dict[str, Any]:
    metadata = get_command_metadata(command_type)
    _require_confirmation(command_type, confirmed)
    normalized_payload = validate_command_payload(command_type, payload or {})
    ensure_preflight_valid(command_type, normalized_payload)
    if (
        is_transactional_command(command_type)
        and device_supports is not None
        and not device_supports("config.transaction")
    ):
        raise HTTPException(
            status_code=409,
            detail="Agent update required: safe configuration transactions are unavailable",
        )
    capability = metadata.get("capability")
    if capability and device_supports is not None and not device_supports(capability):
        raise HTTPException(
            status_code=409,
            detail=f"Device does not support capability '{capability}'",
        )
    return normalized_payload


def expire_old_commands(db: Session) -> int:
    timestamp = now_utc()
    result = db.execute(
        update(DeviceCommand)
        .where(
            DeviceCommand.status.in_(("queued", "sent", "running")),
            DeviceCommand.expires_at.is_not(None),
            DeviceCommand.expires_at < timestamp,
        )
        .values(
            status="expired",
            updated_at=timestamp,
            completed_at=timestamp,
            last_error="Command expired",
        )
    )
    return int(result.rowcount or 0)


def cleanup_device_command_history(
    db: Session,
    device_id: UUID,
    retention_days: int,
    max_per_device: int,
) -> int:
    """Remove old terminal commands without touching active lifecycle records."""
    cutoff = now_utc() - timedelta(days=max(1, retention_days))
    terminal_statuses = tuple(TERMINAL_STATUSES)
    removed_by_age = db.execute(
        delete(DeviceCommand).where(
            DeviceCommand.device_id == device_id,
            DeviceCommand.status.in_(terminal_statuses),
            or_(
                DeviceCommand.completed_at < cutoff,
                and_(
                    DeviceCommand.completed_at.is_(None),
                    DeviceCommand.updated_at < cutoff,
                ),
            ),
        )
    )
    overflow_ids = (
        select(DeviceCommand.id)
        .where(
            DeviceCommand.device_id == device_id,
            DeviceCommand.status.in_(terminal_statuses),
        )
        .order_by(DeviceCommand.created_at.desc(), DeviceCommand.id.desc())
        .offset(max(10, max_per_device))
    )
    removed_overflow = db.execute(
        delete(DeviceCommand).where(DeviceCommand.id.in_(overflow_ids))
    )
    return int(removed_by_age.rowcount or 0) + int(removed_overflow.rowcount or 0)


def requeue_stale_sent_commands(db: Session) -> int:
    timestamp = now_utc()
    result = db.execute(
        update(DeviceCommand)
        .where(
            DeviceCommand.status == "sent",
            DeviceCommand.updated_at < timestamp - COMMAND_DELIVERY_LEASE,
            DeviceCommand.expires_at.is_not(None),
            DeviceCommand.expires_at >= timestamp,
        )
        .values(
            status="queued",
            updated_at=timestamp,
            last_error="Delivery lease expired; command queued for retry",
        )
    )
    return int(result.rowcount or 0)
