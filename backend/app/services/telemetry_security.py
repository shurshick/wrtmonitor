from __future__ import annotations

from typing import Any


SENSITIVE_TELEMETRY_FIELDS = {
    "authorization",
    "device_token",
    "key",
    "password",
    "preshared_key",
    "private_key",
    "secret",
    "token",
}


def sanitize_telemetry_payload(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: sanitize_telemetry_payload(item)
            for key, item in value.items()
            if key.lower() not in SENSITIVE_TELEMETRY_FIELDS
        }
    if isinstance(value, list):
        return [sanitize_telemetry_payload(item) for item in value]
    return value
