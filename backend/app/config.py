import ipaddress
import os
from dataclasses import dataclass
from urllib.parse import urlparse


APP_NAME = "wrtmonitor"
APP_VERSION = "0.1.0-test.2"


@dataclass(frozen=True)
class Settings:
    public_server_url: str | None
    database_url: str
    bind_host: str
    bind_port: int
    jwt_secret: str
    default_locale: str
    allow_insecure_local: bool


def bool_from_env(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def is_private_or_local_host(hostname: str | None) -> bool:
    if not hostname:
        return True
    host = hostname.lower()
    if host in {"localhost", "0.0.0.0"}:
        return True
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return False
    return ip.is_loopback or ip.is_private or ip.is_link_local or ip.is_unspecified


def validate_server_url(value: str, allow_insecure_local: bool = False) -> str:
    normalized = value.strip().rstrip("/")
    parsed = urlparse(normalized)
    if not parsed.scheme or not parsed.netloc:
        raise ValueError("server_url must be an absolute URL")
    local = is_private_or_local_host(parsed.hostname)
    if allow_insecure_local:
        if parsed.scheme not in {"http", "https"}:
            raise ValueError("server_url must use http or https")
        return normalized
    if parsed.scheme != "https":
        raise ValueError("production server_url must use https")
    if local:
        raise ValueError("production server_url must be externally reachable")
    return normalized


def validate_database_url(value: str) -> str:
    parsed = urlparse(value.strip())
    if parsed.scheme != "postgresql+psycopg" or not parsed.hostname or not parsed.path.strip("/"):
        raise ValueError("WRTMONITOR_DATABASE_URL must be postgresql+psycopg://user:password@host:5432/db")
    return value.strip()


def load_settings() -> Settings:
    allow_insecure_local = bool_from_env(os.getenv("WRTMONITOR_ALLOW_INSECURE_LOCAL"), False)
    public_url = os.getenv("WRTMONITOR_PUBLIC_SERVER_URL", "").strip() or None
    if public_url:
        public_url = validate_server_url(public_url, allow_insecure_local)
    return Settings(
        public_server_url=public_url,
        database_url=validate_database_url(
            os.getenv(
                "WRTMONITOR_DATABASE_URL",
                "postgresql+psycopg://wrtmonitor:change-me-db-password@postgres:5432/wrtmonitor",
            )
        ),
        bind_host=os.getenv("WRTMONITOR_BIND_HOST", "0.0.0.0"),
        bind_port=int(os.getenv("WRTMONITOR_BIND_PORT", "8080")),
        jwt_secret=os.getenv("WRTMONITOR_JWT_SECRET", "change-me-long-random-secret"),
        default_locale=os.getenv("WRTMONITOR_DEFAULT_LOCALE", "ru"),
        allow_insecure_local=allow_insecure_local,
    )
