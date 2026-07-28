from typing import Any


COMMAND_CONTRACT_VERSION = 1
TELEMETRY_SCHEMA_CURRENT = 2
TELEMETRY_SCHEMA_SUPPORTED = frozenset({TELEMETRY_SCHEMA_CURRENT})


def telemetry_schema_version(telemetry: dict[str, Any]) -> int:
    """Return the explicit telemetry schema version."""
    if "schema_version" not in telemetry:
        raise ValueError("telemetry schema_version is required")
    raw = telemetry["schema_version"]
    if isinstance(raw, bool):
        raise ValueError("telemetry schema_version must be an integer")
    try:
        version = int(raw)
    except (TypeError, ValueError) as exc:
        raise ValueError("telemetry schema_version must be an integer") from exc
    if version not in TELEMETRY_SCHEMA_SUPPORTED:
        supported = ", ".join(str(item) for item in sorted(TELEMETRY_SCHEMA_SUPPORTED))
        raise ValueError(
            f"unsupported telemetry schema_version {version}; supported: {supported}"
        )
    return version
