from __future__ import annotations

import base64
import binascii
import re
from typing import Any
from urllib.parse import urlsplit

from fastapi import HTTPException

from ..management_options import TIMEZONE_BY_NAME
from .command_common import (
    ALLOWED_DIAGNOSTIC_CHECKS,
    _boolean,
    _normalize_hostname_payload,
    _optional_string,
    _require_string,
    _safe_identifier,
    _string_list,
)


def _normalize_service_payload(payload: dict[str, Any]) -> dict[str, Any]:
    service = _require_string(payload, "service", max_length=32)
    if service not in {"network", "dnsmasq", "firewall", "odhcpd"}:
        raise HTTPException(status_code=400, detail="Service is not allowed")
    return {"service": service}


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


def _maintenance_module(payload: dict[str, Any]) -> dict[str, str]:
    module = str(payload.get("module") or "").strip().lower()
    action = str(payload.get("action") or "").strip().lower()
    if module not in {"storage", "smb", "nfs", "ftp", "dlna", "printer", "modem"}:
        raise HTTPException(status_code=400, detail="Unsupported OpenWrt module")
    if action not in {"install", "enable", "disable", "remove"}:
        raise HTTPException(status_code=400, detail="Unsupported module action")
    if action in {"enable", "disable"} and module in {"storage", "modem"}:
        raise HTTPException(
            status_code=400, detail="This module does not expose a background service"
        )
    return {"module": module, "action": action}


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


__all__ = [
    "_normalize_hostname_payload",
    "_normalize_service_payload",
    "_normalize_timezone_payload",
    "_normalize_ntp_payload",
    "_maintenance_package",
    "_maintenance_module",
    "_maintenance_backup_restore",
    "_maintenance_sysupgrade",
    "_maintenance_cron",
    "_normalize_diagnostics_payload",
    "_normalize_auto_update_payload",
    "_normalize_interval_payload",
]
