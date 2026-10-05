import json
import io
import zipfile
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

import jwt
import pytest

from backend.app.security import decode_access_token, decode_refresh_token
from backend.app.services.hardware_reporting import hardware_report
from backend.app.services.operations import _public_diagnostics
from backend.app.services.operations import build_server_diagnostic_archive
from backend.app.services.telemetry_security import sanitize_telemetry_payload


def test_hardware_report_is_an_allowlist_not_raw_telemetry():
    private = {
        "password": "private-password",
        "wifi_psk": "private-psk",
        "private_key": "private-key",
        "wireguard_private_key": "wg-key",
        "refresh_token": "refresh-secret",
        "session_cookie": "cookie-secret",
        "agent_secret": "agent-secret",
        "ip": "203.0.113.23",
        "mac": "aa:bb:cc:dd:ee:ff",
        "hostname": "private-host",
        "ssid": "private-ssid",
    }
    payload = {
        "hardware": {"model": "netis NX31", **private},
        "cpu": {"cores": 2, "frequencies": [{"cpu": 0, **private}], **private},
        "thermal": {
            "sensors": [
                {
                    "id": "thermal0",
                    "milli_celsius": 50000,
                    "label": "private-label",
                    "trip_points": [{"type": "critical", **private}],
                    **private,
                }
            ],
            "throttling": {"active": False, **private},
        },
    }
    identity = {
        **payload["hardware"],
        "cpu": payload["cpu"],
        "catalog": private,
        "sensors": [{"key": "soc", **private}],
    }
    with patch(
        "backend.app.services.hardware_reporting.hardware_summary",
        return_value=identity,
    ):
        report = hardware_report(
            object(),
            uuid4(),
            payload,
            SimpleNamespace(name="private-name", hostname="private-host", model="NX31"),
        )
    serialized = json.dumps(report)
    for value in (*private.values(), "private-name", "private-label"):
        assert value not in serialized
    assert report["observed"]["thermal"]["sensors"][0]["milli_celsius"] == 50000
    assert report["observed"]["cpu"]["cores"] == 2


def test_support_diagnostics_excludes_freeform_secrets_and_addresses():
    result = _public_diagnostics(
        {
            "route": {"status": "ok", "gateway": "192.168.1.1"},
            "server": {
                "status": "failed",
                "http_status": 503,
                "error": "Authorization: secret",
            },
            "token": "secret",
            "output": "private SSID and PSK",
        }
    )
    assert result == {
        "route": {"status": "ok"},
        "server": {"status": "failed", "http_status": 503},
    }


def test_telemetry_filters_secret_aliases_recursively():
    assert sanitize_telemetry_payload(
        {"nested": [{"Refresh-Token": "secret", "PSK": "secret", "cores": 2}]}
    ) == {"nested": [{"cores": 2}]}


def test_server_archive_excludes_notification_text_and_agent_names():
    db = MagicMock()
    db.scalars.return_value.all.return_value = []
    config = SimpleNamespace(
        telemetry_retention_per_device=1,
        telemetry_metric_retention_days=1,
        command_history_retention_days=1,
        command_history_max_per_device=1,
    )
    with (
        patch(
            "backend.app.services.operations.operation_metrics",
            return_value={
                "agents": {
                    "total": 1,
                    "items": [{"name": "private-host", "token": "private-token"}],
                }
            },
        ),
        patch(
            "backend.app.services.operations.operational_notifications",
            return_value=[
                {
                    "kind": "offline",
                    "message": "private-token",
                    "title": "private-host",
                    "device_id": "private-id",
                }
            ],
        ),
    ):
        data = build_server_diagnostic_archive(db, config)
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        text = "".join(archive.read(name).decode() for name in archive.namelist())
    assert "private-" not in text
    assert "offline" in text


@pytest.mark.parametrize(
    "decoder,kind", [(decode_access_token, "access"), (decode_refresh_token, "refresh")]
)
def test_signed_token_without_expiry_is_rejected(decoder, kind):
    config = SimpleNamespace(
        jwt_secret="test-secret-which-is-longer-than-32-characters"
    )
    token = jwt.encode(
        {"sub": str(uuid4()), "type": kind, "iat": 1, "jti": str(uuid4())},
        config.jwt_secret,
        algorithm="HS256",
    )
    with pytest.raises(jwt.MissingRequiredClaimError):
        decoder(token, config)
