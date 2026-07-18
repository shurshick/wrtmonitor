import ipaddress
import os
from pathlib import Path
from dataclasses import dataclass
from urllib.parse import unquote, urlparse


APP_NAME = "WrtMonitor"
ACCESS_MODEL = "single-owner"


def read_repo_version(version_file: Path | None = None) -> str:
    source = version_file or Path(__file__).resolve().parents[2] / "VERSION"
    if source.is_file():
        version = source.read_text(encoding="utf-8").strip()
        if version:
            return version
    return os.getenv("WRTMONITOR_VERSION", "0.0.0+unknown").strip() or "0.0.0+unknown"


APP_VERSION = read_repo_version()


@dataclass(frozen=True)
class Settings:
    public_server_url: str | None
    database_url: str
    bind_host: str
    bind_port: int
    jwt_secret: str
    default_locale: str
    allow_insecure_local: bool
    allow_insecure_dev_defaults: bool
    enable_api_docs: bool
    telemetry_retention_per_device: int = 100
    telemetry_metric_retention_days: int = 45
    command_history_retention_days: int = 30
    command_history_max_per_device: int = 500


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


def validate_database_url(value: str, allow_insecure_dev_defaults: bool = False) -> str:
    parsed = urlparse(value.strip())
    if (
        parsed.scheme != "postgresql+psycopg"
        or not parsed.hostname
        or not parsed.path.strip("/")
    ):
        raise ValueError(
            "WRTMONITOR_DATABASE_URL must be postgresql+psycopg://user:password@host:5432/db"
        )
    password = unquote(parsed.password or "")
    if not allow_insecure_dev_defaults and (
        not password or password.startswith("change-me")
    ):
        raise ValueError(
            "WRTMONITOR_DATABASE_URL must contain a non-default database password"
        )
    return value.strip()


def validate_jwt_secret(value: str | None) -> str:
    secret = (value or "").strip()
    if secret in {
        "",
        "change-me-long-random-secret",
        "change-me-long-random-jwt-secret",
    }:
        raise ValueError("WRTMONITOR_JWT_SECRET must be set to a unique random value")
    if len(secret) < 32:
        raise ValueError("WRTMONITOR_JWT_SECRET must be at least 32 characters")
    return secret


def load_settings() -> Settings:
    allow_insecure_local = bool_from_env(
        os.getenv("WRTMONITOR_ALLOW_INSECURE_LOCAL"), False
    )
    allow_insecure_dev_defaults = bool_from_env(
        os.getenv("WRTMONITOR_ALLOW_INSECURE_DEV_DEFAULTS"), False
    )
    public_url = os.getenv("WRTMONITOR_PUBLIC_SERVER_URL", "").strip() or None
    if public_url:
        public_url = validate_server_url(public_url, allow_insecure_local)
    return Settings(
        public_server_url=public_url,
        database_url=validate_database_url(
            os.getenv(
                "WRTMONITOR_DATABASE_URL",
                "postgresql+psycopg://wrtmonitor:change-me-db-password@postgres:5432/wrtmonitor",
            ),
            allow_insecure_dev_defaults,
        ),
        bind_host=os.getenv("WRTMONITOR_BIND_HOST", "0.0.0.0"),
        bind_port=int(os.getenv("WRTMONITOR_BIND_PORT", "8080")),
        jwt_secret=validate_jwt_secret(os.getenv("WRTMONITOR_JWT_SECRET")),
        default_locale=os.getenv("WRTMONITOR_DEFAULT_LOCALE", "ru"),
        allow_insecure_local=allow_insecure_local,
        allow_insecure_dev_defaults=allow_insecure_dev_defaults,
        enable_api_docs=bool_from_env(os.getenv("WRTMONITOR_ENABLE_API_DOCS"), False),
        telemetry_retention_per_device=max(
            1, int(os.getenv("WRTMONITOR_TELEMETRY_RETENTION_PER_DEVICE", "100"))
        ),
        telemetry_metric_retention_days=max(
            1, int(os.getenv("WRTMONITOR_TELEMETRY_METRIC_RETENTION_DAYS", "45"))
        ),
        command_history_retention_days=max(
            1, int(os.getenv("WRTMONITOR_COMMAND_HISTORY_RETENTION_DAYS", "30"))
        ),
        command_history_max_per_device=max(
            10, int(os.getenv("WRTMONITOR_COMMAND_HISTORY_MAX_PER_DEVICE", "500"))
        ),
    )
