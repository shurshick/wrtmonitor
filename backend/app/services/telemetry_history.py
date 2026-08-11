from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ..models import DeviceTelemetry, DeviceTelemetryMetric
from .telemetry_common import (
    TELEMETRY_WINDOWS,
    _average_optional,
    _optional_float,
    _optional_int,
    _safe_float,
    _safe_int,
)
from .telemetry_network import normalize_network_summary
from .telemetry_summary import build_telemetry_summary
from .telemetry_wifi import normalize_wifi_summary
from .health_monitoring import build_health_snapshot


def cleanup_device_telemetry(db: Session, device_id: UUID, keep: int) -> None:
    old_ids = [
        row[0]
        for row in db.execute(
            select(DeviceTelemetry.id)
            .where(DeviceTelemetry.device_id == device_id)
            .order_by(DeviceTelemetry.created_at.desc())
            .offset(keep)
        ).all()
    ]
    if old_ids:
        db.execute(delete(DeviceTelemetry).where(DeviceTelemetry.id.in_(old_ids)))


def record_device_telemetry_metric(
    db: Session, device_id: UUID, payload: dict[str, Any], created_at: datetime
) -> DeviceTelemetryMetric:
    summary = build_telemetry_summary(payload)
    rx_bytes = _optional_int(summary.get("traffic_rx_bytes"))
    tx_bytes = _optional_int(summary.get("traffic_tx_bytes"))
    previous = db.scalars(
        select(DeviceTelemetryMetric)
        .where(DeviceTelemetryMetric.device_id == device_id)
        .order_by(DeviceTelemetryMetric.created_at.desc())
        .limit(1)
    ).first()
    rx_bps = tx_bps = None
    if previous is not None:
        elapsed = (created_at - previous.created_at).total_seconds()
        if elapsed > 0:
            if (
                rx_bytes is not None
                and previous.rx_bytes is not None
                and rx_bytes >= previous.rx_bytes
            ):
                rx_bps = round((rx_bytes - previous.rx_bytes) * 8 / elapsed)
            if (
                tx_bytes is not None
                and previous.tx_bytes is not None
                and tx_bytes >= previous.tx_bytes
            ):
                tx_bps = round((tx_bytes - previous.tx_bytes) * 8 / elapsed)
    memory_total = _optional_int(summary.get("memory_total_mb"))
    memory_available = _optional_int(summary.get("memory_available_mb"))
    storage_total = _optional_int(summary.get("storage_total_mb"))
    storage_available = _optional_int(summary.get("storage_available_mb"))
    network = normalize_network_summary(payload)
    wifi = normalize_wifi_summary(payload)
    metric = DeviceTelemetryMetric(
        id=uuid4(),
        device_id=device_id,
        rx_bps=rx_bps,
        tx_bps=tx_bps,
        rx_bytes=rx_bytes,
        tx_bytes=tx_bytes,
        load_1m=_optional_float(summary.get("load_1m")),
        memory_percent=round(
            100 * max(0, memory_total - memory_available) / memory_total, 1
        )
        if memory_total and memory_available is not None
        else None,
        temperature_celsius=_optional_float(summary.get("temperature_celsius")),
        storage_percent=round(
            100 * max(0, storage_total - storage_available) / storage_total, 1
        )
        if storage_total and storage_available is not None
        else None,
        client_count=_optional_int(summary.get("client_count")),
        interfaces={"items": network.get("interfaces") or []},
        wifi={
            "radios": wifi.get("radios") or [],
            "station_count": wifi.get("station_count"),
        },
        created_at=created_at,
    )
    db.add(metric)
    return metric


def cleanup_device_telemetry_metrics(
    db: Session, device_id: UUID, retention_days: int
) -> None:
    cutoff = datetime.now(UTC) - timedelta(days=max(1, retention_days))
    db.execute(
        delete(DeviceTelemetryMetric).where(
            DeviceTelemetryMetric.device_id == device_id,
            DeviceTelemetryMetric.created_at < cutoff,
        )
    )


def device_telemetry_history(
    db: Session,
    device_id: UUID,
    limit: int = 60,
    range_name: str | None = None,
) -> list[dict[str, Any]]:
    if range_name:
        window, target_points = TELEMETRY_WINDOWS.get(
            range_name, TELEMETRY_WINDOWS["live"]
        )
        rows = list(
            db.scalars(
                select(DeviceTelemetryMetric)
                .where(
                    DeviceTelemetryMetric.device_id == device_id,
                    DeviceTelemetryMetric.created_at >= datetime.now(UTC) - window,
                )
                .order_by(DeviceTelemetryMetric.created_at.asc())
            ).all()
        )
        if rows and hasattr(rows[0], "rx_bps"):
            return downsample_telemetry_metrics(rows, target_points)
    metric_rows = list(
        reversed(
            list(
                db.scalars(
                    select(DeviceTelemetryMetric)
                    .where(DeviceTelemetryMetric.device_id == device_id)
                    .order_by(DeviceTelemetryMetric.created_at.desc())
                    .limit(max(2, min(limit, 360)))
                ).all()
            )
        )
    )
    if metric_rows and hasattr(metric_rows[0], "rx_bps"):
        return [metric_history_point(row) for row in metric_rows]
    rows = list(
        db.scalars(
            select(DeviceTelemetry)
            .where(DeviceTelemetry.device_id == device_id)
            .order_by(DeviceTelemetry.created_at.desc())
            .limit(max(2, min(limit, 120)))
        ).all()
    )
    return build_telemetry_history(reversed(rows))


def metric_history_point(row: DeviceTelemetryMetric) -> dict[str, Any]:
    return {
        "created_at": row.created_at.isoformat(),
        "rx_bps": row.rx_bps,
        "tx_bps": row.tx_bps,
        "rx_bytes": row.rx_bytes,
        "tx_bytes": row.tx_bytes,
        "load_1m": round(row.load_1m, 2) if row.load_1m is not None else None,
        "memory_percent": round(row.memory_percent, 1)
        if row.memory_percent is not None
        else None,
        "temperature_celsius": round(row.temperature_celsius, 1)
        if row.temperature_celsius is not None
        else None,
        "storage_percent": round(row.storage_percent, 1)
        if row.storage_percent is not None
        else None,
        "client_count": row.client_count,
    }


def downsample_telemetry_metrics(
    rows: list[DeviceTelemetryMetric], target_points: int
) -> list[dict[str, Any]]:
    if len(rows) <= target_points:
        return [metric_history_point(row) for row in rows]
    bucket_size = max(1, (len(rows) + target_points - 1) // target_points)
    points: list[dict[str, Any]] = []
    for start in range(0, len(rows), bucket_size):
        bucket = rows[start : start + bucket_size]
        last = bucket[-1]
        points.append(
            {
                "created_at": last.created_at.isoformat(),
                "rx_bps": _average_optional(bucket, "rx_bps", 0),
                "tx_bps": _average_optional(bucket, "tx_bps", 0),
                "rx_bytes": last.rx_bytes,
                "tx_bytes": last.tx_bytes,
                "load_1m": _average_optional(bucket, "load_1m", 2),
                "memory_percent": _average_optional(bucket, "memory_percent", 1),
                "temperature_celsius": _average_optional(
                    bucket, "temperature_celsius", 1
                ),
                "storage_percent": _average_optional(bucket, "storage_percent", 1),
                "client_count": _average_optional(bucket, "client_count", 0),
            }
        )
    return points


def telemetry_alerts(
    payload: dict[str, Any] | None, age_seconds: int | None
) -> list[dict[str, str]]:
    return build_health_snapshot(payload, age_seconds)["alerts"]


def build_telemetry_history(
    rows: Any,
) -> list[dict[str, Any]]:
    points: list[dict[str, Any]] = []
    previous: tuple[datetime, int, int] | None = None
    for row in rows:
        payload = row.payload if isinstance(row.payload, dict) else {}
        summary = build_telemetry_summary(payload)
        rx_bytes = _safe_int(summary.get("traffic_rx_bytes"))
        tx_bytes = _safe_int(summary.get("traffic_tx_bytes"))
        rx_bps = tx_bps = 0
        if previous is not None:
            previous_at, previous_rx, previous_tx = previous
            elapsed = (row.created_at - previous_at).total_seconds()
            if elapsed > 0:
                if rx_bytes >= previous_rx:
                    rx_bps = round((rx_bytes - previous_rx) * 8 / elapsed)
                if tx_bytes >= previous_tx:
                    tx_bps = round((tx_bytes - previous_tx) * 8 / elapsed)
        memory_total = _safe_int(summary.get("memory_total_mb"))
        memory_available = _safe_int(summary.get("memory_available_mb"))
        storage_total = _safe_int(summary.get("storage_total_mb"))
        storage_available = _safe_int(summary.get("storage_available_mb"))
        points.append(
            {
                "created_at": row.created_at.isoformat(),
                "rx_bps": rx_bps,
                "tx_bps": tx_bps,
                "rx_bytes": rx_bytes,
                "tx_bytes": tx_bytes,
                "load_1m": _safe_float(summary.get("load_1m")),
                "memory_percent": round(
                    100 * max(0, memory_total - memory_available) / memory_total, 1
                )
                if memory_total
                else 0,
                "temperature_celsius": _optional_float(
                    summary.get("temperature_celsius")
                ),
                "storage_percent": round(
                    100 * max(0, storage_total - storage_available) / storage_total, 1
                )
                if storage_total
                else None,
                "client_count": _safe_int(summary.get("client_count")),
            }
        )
        previous = (row.created_at, rx_bytes, tx_bytes)
    return points


__all__ = [
    "cleanup_device_telemetry",
    "record_device_telemetry_metric",
    "cleanup_device_telemetry_metrics",
    "device_telemetry_history",
    "metric_history_point",
    "downsample_telemetry_metrics",
    "telemetry_alerts",
    "build_telemetry_history",
]
