from __future__ import annotations

from datetime import timedelta
from ipaddress import (
    AddressValueError,
    IPv4Address,
)
from typing import Any

from fastapi import HTTPException

from .command_registry import COMMAND_REGISTRY

COMMAND_DELIVERY_LEASE = timedelta(seconds=45)
TERMINAL_STATUSES = {"success", "failed", "expired", "cancelled"}
ALLOWED_DIAGNOSTIC_CHECKS = {"server", "dns", "route", "wifi", "dependencies"}
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


_IDENTIFIER_CHOICES = {
    r"(?:ACCEPT|REJECT|DROP)": {"ACCEPT", "REJECT", "DROP"},
    r"(?:TERM|HUP|KILL)": {"TERM", "HUP", "KILL"},
    r"(?:all|tcp|udp|icmp)": {"all", "tcp", "udp", "icmp"},
    r"(?:server|client)": {"server", "client"},
    r"(?:start|stop|restart|enable|disable)": {
        "start",
        "stop",
        "restart",
        "enable",
        "disable",
    },
    r"(?:NOHT|HT(?:20|40[+-]?)|VHT(?:20|40|80|160)|HE(?:20|40|80|160))": {
        "NOHT",
        "HT20",
        "HT40",
        "HT40+",
        "HT40-",
        "VHT20",
        "VHT40",
        "VHT80",
        "VHT160",
        "HE20",
        "HE40",
        "HE80",
        "HE160",
    },
}
_IDENTIFIER_CHARACTERS = {
    r"[A-Za-z0-9_.-]+": (
        "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_.-",
        1,
        255,
    ),
    r"[A-Za-z0-9_.-]{1,64}": (
        "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_.-",
        1,
        64,
    ),
    r"[A-Za-z0-9_.:-]+": (
        "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_.:-",
        1,
        255,
    ),
    r"[A-Za-z0-9_.@:-]+": (
        "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_.@:-",
        1,
        255,
    ),
    r"[A-Za-z0-9_.@\[\]-]+": (
        "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_.@[]-",
        1,
        255,
    ),
    r"[A-Za-z0-9_@.\[\]-]+": (
        "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_@.[]-",
        1,
        255,
    ),
    r"[A-Za-z0-9_+./-]+": (
        "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_+./-",
        1,
        255,
    ),
    r"[A-Za-z0-9_+,:./<>-]+": (
        "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_+,:./<>-",
        1,
        255,
    ),
    r"[A-Za-z0-9_.@-]+": (
        "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_.@-",
        1,
        255,
    ),
}


def _matches_identifier_rule(value: str, pattern: str) -> bool:
    if choices := _IDENTIFIER_CHOICES.get(pattern):
        return value in choices
    if rule := _IDENTIFIER_CHARACTERS.get(pattern):
        allowed, minimum, maximum = rule
        return minimum <= len(value) <= maximum and all(
            char in allowed for char in value
        )
    if pattern == r"[A-Z]{2}":
        return (
            len(value) == 2 and value.isascii() and value.isalpha() and value.isupper()
        )
    if pattern == r"[0-9A-Fa-f]{4}":
        return len(value) == 4 and all(
            char in "0123456789abcdefABCDEF" for char in value
        )
    if pattern == r"[1-9][0-9]*[mh]":
        return (
            len(value) >= 2
            and value[0] in "123456789"
            and value[-1] in "mh"
            and value[:-1].isdigit()
        )
    if pattern == r"(?:[0-9a-f]{2}:){5}[0-9a-f]{2}":
        parts = value.split(":")
        return len(parts) == 6 and all(
            len(part) == 2 and all(char in "0123456789abcdef" for char in part)
            for part in parts
        )
    if pattern == r"[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?":
        allowed = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.-"
        return (
            value[0].isalnum()
            and value[-1].isalnum()
            and all(char in allowed for char in value)
        )
    if pattern == r"[A-Za-z0-9_][A-Za-z0-9_-]*":
        allowed = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-"
        return value[0] in allowed.replace("-", "") and all(
            char in allowed for char in value
        )
    if pattern == r"[A-Za-z0-9_.@-]+(?::[ut](?:\*)?)?":
        base, separator, suffix = value.partition(":")
        allowed = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_.@-"
        return (
            bool(base)
            and all(char in allowed for char in base)
            and (not separator or suffix in {"u", "t", "u*", "t*"})
        )
    raise RuntimeError(f"Unsupported identifier validation rule: {pattern}")


def _safe_identifier(value: str, field: str, pattern: str) -> str:
    if not value or len(value) > 255 or not _matches_identifier_rule(value, pattern):
        raise HTTPException(
            status_code=400, detail=f"Field '{field}' has invalid format"
        )
    return value


def _boolean(payload: dict[str, Any], key: str, *, default: bool | None = None) -> bool:
    value = payload.get(key, default)
    if not isinstance(value, bool):
        raise HTTPException(status_code=400, detail=f"Field '{key}' must be boolean")
    return value


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
    values = (
        raw
        if isinstance(raw, list)
        else str(raw).replace(",", " ").replace(";", " ").split()
    )
    result = [str(value).strip() for value in values if str(value).strip()]
    if required and not result:
        raise HTTPException(status_code=400, detail=f"Field '{key}' is required")
    if len(result) > 8:
        raise HTTPException(
            status_code=400, detail=f"Field '{key}' contains too many values"
        )
    return result


def _name(payload: dict[str, Any], key: str = "name") -> str:
    return _safe_identifier(
        _require_string(payload, key, max_length=64), key, r"[A-Za-z0-9_.-]+"
    )


def _uci_section(payload: dict[str, Any]) -> str:
    section = _optional_string(payload, "section") or ""
    if section:
        valid = _matches_identifier_rule(section, r"[A-Za-z0-9_.-]+")
        if section.startswith("@") and section.endswith("]") and "[" in section:
            section_type, index = section[1:-1].split("[", 1)
            allowed = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-"
            valid = (
                bool(section_type)
                and all(char in allowed for char in section_type)
                and index.isdigit()
            )
        if not valid:
            raise HTTPException(status_code=400, detail="Invalid UCI section")
    return section


def _normalize_hostname_payload(payload: dict[str, Any]) -> dict[str, Any]:
    hostname = _require_string(payload, "hostname", max_length=63)
    return {
        "hostname": _safe_identifier(
            hostname, "hostname", r"[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?"
        )
    }


__all__ = [
    "get_command_metadata",
    "_require_confirmation",
    "_require_string",
    "_optional_string",
    "_safe_identifier",
    "_boolean",
    "_ipv4",
    "_integer",
    "_string_list",
    "_name",
    "_uci_section",
    "_normalize_hostname_payload",
]
