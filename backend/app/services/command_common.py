from __future__ import annotations

from datetime import timedelta
from ipaddress import (
    AddressValueError,
    IPv4Address,
)
import re
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


def _safe_identifier(value: str, field: str, pattern: str) -> str:
    if not re.fullmatch(pattern, value):
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
    values = raw if isinstance(raw, list) else re.split(r"[\s,;]+", str(raw).strip())
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
    if section and not re.fullmatch(
        r"(?:@[A-Za-z0-9_-]+\[[0-9]+\]|[A-Za-z0-9_.-]+)", section
    ):
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
