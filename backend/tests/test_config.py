import pytest

from backend.app.config import validate_database_url, validate_server_url


def test_https_server_url_is_valid():
    assert validate_server_url("https://monitor.example.ru/") == "https://monitor.example.ru"


def test_http_server_url_is_rejected_for_production():
    with pytest.raises(ValueError):
        validate_server_url("http://monitor.example.ru")


def test_postgresql_url_is_required():
    with pytest.raises(ValueError):
        validate_database_url("sqlite:///tmp.db")
