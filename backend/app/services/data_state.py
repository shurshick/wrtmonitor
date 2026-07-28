from __future__ import annotations

from datetime import datetime
from typing import Any, Literal


DataStateKind = Literal["configured", "observed", "unsupported", "stale", "error"]
DATA_STATE_KINDS = frozenset(
    {"configured", "observed", "unsupported", "stale", "error"}
)


def data_state(
    kind: DataStateKind,
    *,
    reason: str | None = None,
    observed_at: datetime | str | None = None,
    age_seconds: int | None = None,
) -> dict[str, Any]:
    if kind not in DATA_STATE_KINDS:
        raise ValueError(f"invalid data state: {kind}")
    timestamp = (
        observed_at.isoformat() if isinstance(observed_at, datetime) else observed_at
    )
    return {
        "kind": kind,
        "reason": reason,
        "observed_at": timestamp,
        "age_seconds": age_seconds,
    }


def telemetry_data_state(
    payload: dict[str, Any] | None,
    *,
    observed_at: datetime | None,
    age_seconds: int | None,
    stale_after_seconds: int,
) -> dict[str, Any]:
    if payload is None:
        return data_state("stale", reason="never_received")
    if age_seconds is not None and age_seconds > stale_after_seconds:
        return data_state(
            "stale",
            reason="observation_expired",
            observed_at=observed_at,
            age_seconds=age_seconds,
        )
    errors = payload.get("collection_errors")
    if isinstance(errors, list) and errors:
        return data_state(
            "error",
            reason="collection_failed",
            observed_at=observed_at,
            age_seconds=age_seconds,
        )
    return data_state("observed", observed_at=observed_at, age_seconds=age_seconds)


def subsystem_data_state(
    value: Any,
    *,
    parent_state: dict[str, Any],
    available: bool | None = None,
    configured: bool = False,
) -> dict[str, Any]:
    if parent_state["kind"] == "stale":
        return dict(parent_state)
    if available is False:
        return data_state("unsupported", reason="not_supported_by_router")
    if isinstance(value, dict) and (
        value.get("error") or value.get("status") == "error"
    ):
        return data_state(
            "error", reason=str(value.get("error") or "collection_failed")
        )
    if value is None:
        return data_state(
            "configured" if configured else "unsupported", reason="not_observed"
        )
    return data_state(
        "observed",
        observed_at=parent_state.get("observed_at"),
        age_seconds=parent_state.get("age_seconds"),
    )
