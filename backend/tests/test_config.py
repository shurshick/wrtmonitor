from pathlib import Path
from uuid import uuid4

import pytest

from backend.app.config import (
    load_settings,
    read_repo_version,
    validate_database_url,
    validate_jwt_secret,
    validate_server_url,
)
from backend.app.security import (
    create_access_token,
    create_refresh_token,
    decode_access_token,
    decode_refresh_token,
)


def test_https_server_url_is_valid():
    assert (
        validate_server_url("https://monitor.example.ru/")
        == "https://monitor.example.ru"
    )


def test_http_server_url_is_rejected_for_production():
    with pytest.raises(ValueError):
        validate_server_url("http://monitor.example.ru")


def test_postgresql_url_is_required():
    with pytest.raises(ValueError):
        validate_database_url("sqlite:///tmp.db")


def test_default_database_password_is_rejected():
    with pytest.raises(ValueError):
        validate_database_url(
            "postgresql+psycopg://wrtmonitor:change-me-db-password@postgres:5432/wrtmonitor"
        )


def test_default_database_password_requires_explicit_dev_flag():
    assert (
        validate_database_url(
            "postgresql+psycopg://wrtmonitor:change-me-db-password@postgres:5432/wrtmonitor",
            allow_insecure_dev_defaults=True,
        )
        == "postgresql+psycopg://wrtmonitor:change-me-db-password@postgres:5432/wrtmonitor"
    )


def test_default_jwt_secret_is_rejected():
    with pytest.raises(ValueError):
        validate_jwt_secret("change-me-long-random-secret")


def test_read_repo_version_reads_packaged_file(tmp_path: Path) -> None:
    version_file = tmp_path / "VERSION"
    version_file.write_text("1.2.3-rc1\n", encoding="utf-8")

    assert read_repo_version(version_file) == "1.2.3-rc1"


def test_read_repo_version_uses_environment_fallback(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("WRTMONITOR_VERSION", "1.2.3-fallback")

    assert read_repo_version(tmp_path / "missing-version") == "1.2.3-fallback"


def test_read_repo_version_has_safe_unknown_fallback(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.delenv("WRTMONITOR_VERSION", raising=False)

    assert read_repo_version(tmp_path / "missing-version") == "0.0.0+unknown"


def test_access_and_refresh_tokens_are_not_interchangeable():
    config = load_settings()
    user_id = uuid4()
    access = create_access_token(user_id, "owner", config)
    refresh = create_refresh_token(user_id, "owner", config)
    assert decode_access_token(access, config)["sub"] == str(user_id)
    assert decode_refresh_token(refresh, config)["sub"] == str(user_id)
    with pytest.raises(Exception):
        decode_access_token(refresh, config)
    with pytest.raises(Exception):
        decode_refresh_token(access, config)
