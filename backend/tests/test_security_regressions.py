from unittest.mock import patch

import pytest
from fastapi import HTTPException

from backend.app.services.command_common import _safe_identifier
from backend.app.services.command_vpn import _normalize_wireguard_peer_payload
from backend.app.services.firmware_catalog import firmware_catalog
from backend.app.web import routes_account


def test_identifier_is_bounded_before_regex():
    with patch("backend.app.services.command_common.re.fullmatch") as match:
        with pytest.raises(HTTPException):
            _safe_identifier("1" * 256, "leasetime", r"[1-9][0-9]*[mh]")
        match.assert_not_called()


def test_wireguard_endpoint_is_bounded():
    with pytest.raises(HTTPException, match="endpoint"):
        _normalize_wireguard_peer_payload(
            {"allowed_ips": ["0.0.0.0/0"], "endpoint": "a" * 256 + ":1234"}
        )


def test_catalog_does_not_expose_exception_details():
    with patch(
        "backend.app.services.firmware_catalog._overview",
        side_effect=ValueError("private /server/path credential"),
    ):
        result = firmware_catalog(
            {
                "board": {
                    "board_name": "netis,nx31",
                    "release": {"version": "25.12.4", "target": "mediatek/filogic"},
                }
            }
        )
    assert result["status"] == "error"
    assert "private" not in result["error"]
    assert "unavailable" in result["error"]


def test_backup_download_cannot_escape_backup_directory(tmp_path, monkeypatch):
    backup_directory = tmp_path / "backups"
    backup_directory.mkdir()
    outside = tmp_path / "outside.dump"
    outside.write_bytes(b"private data")
    monkeypatch.setattr(routes_account, "BACKUP_DIRECTORY", backup_directory)
    monkeypatch.setattr(routes_account, "web_user_from_session", lambda *args: object())
    with pytest.raises(HTTPException) as failure:
        routes_account.web_download_database_backup(
            filename="../outside.dump",
            config=object(),
            db=object(),
            wrtmonitor_session="session",
        )
    assert failure.value.status_code == 404
    (backup_directory / "valid.dump").write_bytes(b"valid backup")
    response = routes_account.web_download_database_backup(
        filename="valid.dump",
        config=object(),
        db=object(),
        wrtmonitor_session="session",
    )
    assert response.path == (backup_directory / "valid.dump").resolve()
