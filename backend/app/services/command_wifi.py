from __future__ import annotations

import re
from typing import Any

from fastapi import HTTPException

from .command_common import (
    _boolean,
    _integer,
    _optional_string,
    _require_string,
    _safe_identifier,
    _string_list,
)


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
    if "enabled" in payload:
        result["enabled"] = _boolean(payload, "enabled")
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


def _normalize_guest_payload(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload.get("enabled"), bool):
        raise HTTPException(
            status_code=400, detail="Field 'enabled' must be provided as boolean"
        )
    result: dict[str, Any] = {"enabled": payload["enabled"]}
    if payload["enabled"]:
        ssid = _optional_string(payload, "ssid")
        password = _optional_string(payload, "password")
        if ssid:
            result["ssid"] = _require_string(payload, "ssid", max_length=32)
        if password:
            result["password"] = _require_string(
                payload, "password", min_length=8, max_length=63
            )
    radio = _optional_string(payload, "radio")
    if radio:
        result["radio"] = _safe_identifier(radio, "radio", r"[A-Za-z0-9_.@\[\]-]+")
    return result


__all__ = [
    "_normalize_wifi_enabled_payload",
    "_normalize_wifi_ssid_payload",
    "_normalize_wifi_password_payload",
    "_normalize_wifi_channel_payload",
    "_normalize_wifi_country_payload",
    "_wifi_selector",
    "_wifi_encryption",
    "_wifi_key",
    "_normalize_wifi_radio_payload",
    "_normalize_wifi_add_ssid_payload",
    "_normalize_wifi_update_ssid_payload",
    "_normalize_wifi_schedule_payload",
    "_normalize_wifi_mesh_payload",
    "_normalize_guest_payload",
]
