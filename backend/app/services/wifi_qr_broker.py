from __future__ import annotations

from datetime import UTC, datetime, timedelta
from threading import Lock
from typing import Any
from uuid import UUID


_LOCK = Lock()
_RESULTS: dict[UUID, tuple[datetime, dict[str, Any]]] = {}
_TTL = timedelta(seconds=30)


def publish_wifi_qr_result(command_id: UUID, result: dict[str, Any]) -> None:
    """Keep a one-time Wi-Fi QR result in process memory only."""
    now = datetime.now(UTC)
    with _LOCK:
        _purge(now)
        _RESULTS[command_id] = (now + _TTL, dict(result))


def consume_wifi_qr_result(command_id: UUID) -> dict[str, Any] | None:
    now = datetime.now(UTC)
    with _LOCK:
        _purge(now)
        item = _RESULTS.pop(command_id, None)
    return dict(item[1]) if item else None


def persistent_wifi_qr_result(status: str, result: dict[str, Any]) -> dict[str, Any]:
    """Return the only QR command data that may be written to PostgreSQL."""
    if status in {"done", "success"}:
        return {"message": "One-time Wi-Fi QR result delivered"}
    error_detail = result.get("error_detail")
    if isinstance(error_detail, dict):
        return {
            "error_detail": {
                "code": str(error_detail.get("code") or "wifi_qr_failed"),
                "message": str(
                    error_detail.get("message") or "Wi-Fi QR is unavailable"
                ),
            }
        }
    return {
        "error": str(
            result.get("error") or result.get("message") or "Wi-Fi QR is unavailable"
        )
    }


def _purge(now: datetime) -> None:
    expired = [key for key, (expires_at, _) in _RESULTS.items() if expires_at <= now]
    for key in expired:
        _RESULTS.pop(key, None)


__all__ = [
    "consume_wifi_qr_result",
    "persistent_wifi_qr_result",
    "publish_wifi_qr_result",
]
