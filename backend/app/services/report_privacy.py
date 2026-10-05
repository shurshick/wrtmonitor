from typing import Any


def public_fields(value: Any, schema: Any) -> Any:
    """Export only declared fields; never forward unknown nested telemetry."""
    if isinstance(schema, dict):
        source = value if isinstance(value, dict) else {}
        return {
            key: public_fields(source[key], child)
            for key, child in schema.items()
            if key in source
        }
    if isinstance(schema, list):
        return (
            [public_fields(item, schema[0]) for item in value]
            if isinstance(value, list)
            else []
        )
    return value if isinstance(value, (str, int, float, bool, type(None))) else None


def fields(*names: str) -> dict[str, None]:
    return dict.fromkeys(names)


HARDWARE_FIELDS = fields(
    "state", "model", "board_name", "target", "package_arch", "architecture"
) | {"compatible": [None]}
CPU_FIELDS = fields(
    "model", "observed_model", "architecture", "cores", "current_khz", "max_khz"
) | {
    "compatible": [None],
    "frequencies": [fields("cpu", "current_khz", "min_khz", "max_khz", "governor")],
}
SENSOR_FIELDS = fields(
    "id",
    "type",
    "subsystem",
    "role",
    "milli_celsius",
    "warning_milli_celsius",
    "critical_milli_celsius",
    "source",
    "state",
) | {"trip_points": [fields("type", "milli_celsius", "hysteresis_milli_celsius")]}
THROTTLING_FIELDS = fields("state", "active", "count")
IDENTITY_FIELDS = HARDWARE_FIELDS | {
    "cpu": CPU_FIELDS,
    "catalog": fields(
        "profile_key",
        "vendor",
        "model",
        "soc_vendor",
        "soc_model",
        "cpu_vendor",
        "cpu_model",
        "cpu_architecture",
        "cpu_cores",
        "cpu_max_mhz",
        "catalog_version",
        "origin",
        "verified",
        "observation_count",
    ),
    "sensors": [
        fields(
            "key",
            "role",
            "current_milli_celsius",
            "min_milli_celsius",
            "max_milli_celsius",
            "sample_count",
            "source_count",
            "warning_milli_celsius",
            "critical_milli_celsius",
            "state",
            "thermal_status",
            "headroom_milli_celsius",
        )
    ],
    "raw_sensor_count": None,
    "thermal_health": None,
    "throttling": THROTTLING_FIELDS,
    "match": fields("method", "confidence"),
}
