from uuid import uuid4

from backend.app.services.wifi_qr_broker import (
    consume_wifi_qr_result,
    persistent_wifi_qr_result,
    publish_wifi_qr_result,
)


def test_wifi_qr_result_is_one_time_and_memory_only() -> None:
    command_id = uuid4()
    payload = {
        "wifi_uri": "WIFI:T:WPA;S:Home;P:temporary-secret;;",
        "ssid": "Home",
        "security": "WPA",
    }
    publish_wifi_qr_result(command_id, payload)

    assert consume_wifi_qr_result(command_id) == payload
    assert consume_wifi_qr_result(command_id) is None


def test_wifi_qr_payload_does_not_share_mutable_input() -> None:
    command_id = uuid4()
    payload = {"wifi_uri": "WIFI:T:nopass;S:Guest;;;"}
    publish_wifi_qr_result(command_id, payload)
    payload["wifi_uri"] = "changed"

    assert consume_wifi_qr_result(command_id) == {
        "wifi_uri": "WIFI:T:nopass;S:Guest;;;"
    }


def test_wifi_qr_secret_is_never_persisted_even_on_failure() -> None:
    secret = "WIFI:T:WPA;S:Home;P:must-not-reach-postgres;;"

    assert persistent_wifi_qr_result("success", {"wifi_uri": secret}) == {
        "message": "One-time Wi-Fi QR result delivered"
    }
    failed = persistent_wifi_qr_result(
        "failed", {"wifi_uri": secret, "error": "key unavailable"}
    )
    assert failed == {"error": "key unavailable"}
    assert secret not in str(failed)
