from datetime import UTC, datetime

from backend.app.services.data_state import subsystem_data_state, telemetry_data_state


def test_missing_telemetry_is_stale_not_empty_observation() -> None:
    state = telemetry_data_state(
        None, observed_at=None, age_seconds=None, stale_after_seconds=300
    )
    assert state == {
        "kind": "stale",
        "reason": "never_received",
        "observed_at": None,
        "age_seconds": None,
    }


def test_observed_unsupported_and_error_are_distinct() -> None:
    observed = telemetry_data_state(
        {"schema_version": 2},
        observed_at=datetime(2026, 7, 28, tzinfo=UTC),
        age_seconds=4,
        stale_after_seconds=300,
    )
    assert observed["kind"] == "observed"
    assert subsystem_data_state({}, parent_state=observed, available=False)["kind"] == "unsupported"
    assert subsystem_data_state({"error": "ubus failed"}, parent_state=observed)["kind"] == "error"


def test_stale_parent_wins_over_subsystem_payload() -> None:
    stale = telemetry_data_state(
        {"schema_version": 2},
        observed_at=datetime(2026, 7, 28, tzinfo=UTC),
        age_seconds=301,
        stale_after_seconds=300,
    )
    assert subsystem_data_state({"available": True}, parent_state=stale)["kind"] == "stale"
