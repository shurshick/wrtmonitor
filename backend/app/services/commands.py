from __future__ import annotations

from datetime import UTC, datetime, timedelta
from ipaddress import IPv4Address, AddressValueError
import re
from typing import Any, Callable
from uuid import UUID, uuid4

from fastapi import HTTPException
from sqlalchemy import update
from sqlalchemy.orm import Session

from ..models import DeviceCommand


COMMAND_TTL = timedelta(minutes=5)
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
    if command_type == "network.interface_restart":
        return _normalize_interface_payload(normalized_payload)
    if command_type == "system.set_hostname":
        return _normalize_hostname_payload(normalized_payload)
    if command_type == "system.restart_service":
        return _normalize_service_payload(normalized_payload)
    if command_type == "dhcp.set_lease":
        return _normalize_dhcp_lease_payload(normalized_payload)
    if command_type == "dhcp.delete_lease":
        return _normalize_dhcp_lease_payload(normalized_payload, delete=True)
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
    elif command_type == "network.interface_restart":
        payload = {"interface": interface}
    elif command_type == "system.set_hostname":
        payload = {"hostname": hostname}
    elif command_type == "system.restart_service":
        payload = {"service": service}
    elif command_type == "dhcp.set_lease":
        payload = {"mac": mac, "ip": ip, "hostname": hostname}
    elif command_type == "dhcp.delete_lease":
        payload = {"mac": mac}
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
    return mask_secrets(result, secret_fields)


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
    command = DeviceCommand(
        id=uuid4(),
        device_id=device_id,
        command_type=command_type,
        payload=payload,
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
