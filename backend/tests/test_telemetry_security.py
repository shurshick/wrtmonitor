from backend.app.services.telemetry_security import sanitize_telemetry_payload


def test_telemetry_sanitizer_removes_nested_secrets():
    payload = {
        "wireless_status": {"interfaces": [{"ssid": "Home", "key": "wifi-secret"}]},
        "vpn": {
            "public_key": "safe-public-key",
            "private_key": "private-secret",
        },
        "clients": [{"token": "secret", "mac": "00:11:22:33:44:55"}],
    }

    sanitized = sanitize_telemetry_payload(payload)

    assert sanitized["wireless_status"]["interfaces"] == [{"ssid": "Home"}]
    assert sanitized["vpn"] == {"public_key": "safe-public-key"}
    assert sanitized["clients"] == [{"mac": "00:11:22:33:44:55"}]
