from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_hardware_telemetry_uses_device_tree_cpufreq_thermal_and_hwmon():
    system = (ROOT / "lib" / "telemetry_system.sh").read_text(encoding="utf-8")
    payload = (ROOT / "lib" / "telemetry.sh").read_text(encoding="utf-8")

    assert "hardware_identity_json" in system
    assert "/sys/firmware/devicetree/base" in system
    assert "scaling_cur_freq" in system
    assert "/sys/class/thermal/thermal_zone*" in system
    assert "/sys/class/hwmon/hwmon*" in system
    assert '"hardware":%s' in payload


def test_thermal_contract_keeps_legacy_primary_value_and_adds_sensor_list():
    source = (ROOT / "lib" / "telemetry_system.sh").read_text(encoding="utf-8")

    assert '"milli_celsius":%s' in source
    assert '"sensor_count":%s' in source
    assert '"sensors":[%s]' in source
    assert '"state":"unsupported"' in source
    assert "warning_milli_celsius" in source
    assert "critical_milli_celsius" in source
    assert '\\"trip_points\\":[' in source
    assert '\\"milli_celsius\\":$trip_temp' in source
    assert '"throttling"' in source
    assert "thermal_pressure" in source
