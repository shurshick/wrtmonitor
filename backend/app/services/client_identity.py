from __future__ import annotations

import re
from typing import Any

from fastapi import HTTPException
import pymanuf


CLIENT_DEVICE_TYPES = {
    "phone",
    "tablet",
    "computer",
    "tv",
    "speaker",
    "camera",
    "printer",
    "storage",
    "router",
    "iot",
    "unknown",
}


def normalize_mac(value: str) -> str:
    mac = value.strip().lower().replace("-", ":")
    if not re.fullmatch(r"(?:[0-9a-f]{2}:){5}[0-9a-f]{2}", mac):
        raise HTTPException(status_code=422, detail="Invalid client MAC address")
    return mac


def inferred_vendor(mac: str, reported: Any = None) -> str | None:
    if reported:
        return str(reported)[:160]
    first_octet = int(mac[:2], 16)
    if first_octet & 2:
        return "Private/randomized MAC"
    try:
        return pymanuf.lookup(mac) or None
    except (KeyError, TypeError, ValueError):
        return None


def infer_device_type(*values: Any) -> str:
    identity = " ".join(str(value).lower() for value in values if value)
    rules = (
        ("tv", ("smart tv", "android tv", "television", "chromecast", "fire tv")),
        ("phone", ("phone", "iphone", "android", "redmi", "poco", "mobile")),
        ("tablet", ("tablet", "ipad", "tab ")),
        (
            "computer",
            (
                "desktop",
                "computer",
                "laptop",
                "notebook",
                "macbook",
                "windows",
                "workstation",
            ),
        ),
        (
            "speaker",
            ("speaker", "alexa", "echo dot", "homepod", "яндекс станц", "sberboom"),
        ),
        ("camera", ("camera", "cam ", "ipcam", "doorbell", "видеокамер")),
        ("printer", ("printer", "laserjet", "officejet", "pixma", "epson")),
        ("storage", ("nas", "synology", "qnap", "truenas")),
        ("router", ("router", "openwrt", "gateway", "access point")),
        (
            "iot",
            (
                "iot",
                "sensor",
                "socket",
                "plug",
                "bulb",
                "thermostat",
                "esp32",
                "esp8266",
            ),
        ),
    )
    for device_type, markers in rules:
        if any(marker in identity for marker in markers):
            return device_type
    return "unknown"


def validate_device_type(value: str | None) -> str:
    normalized = str(value or "unknown").strip().lower()
    if normalized not in CLIENT_DEVICE_TYPES:
        raise HTTPException(status_code=422, detail="Invalid client device type")
    return normalized
