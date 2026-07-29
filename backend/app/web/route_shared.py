import base64  # noqa: F401
import binascii  # noqa: F401
from datetime import UTC, datetime
import json  # noqa: F401
from pathlib import Path
import secrets  # noqa: F401
import segno  # noqa: F401
from uuid import UUID, uuid4  # noqa: F401

from fastapi import (  # noqa: F401
    APIRouter,
    Cookie,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    UploadFile,
)
from fastapi.responses import (  # noqa: F401
    FileResponse,
    HTMLResponse,
    JSONResponse,
    RedirectResponse,
    Response,
)
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select  # noqa: F401
from sqlalchemy.orm import Session  # noqa: F401

from ..config import APP_NAME, APP_VERSION, Settings  # noqa: F401
from ..db import get_db  # noqa: F401
from ..management_options import (  # noqa: F401
    NETMASK_OPTIONS,
    TIMEZONE_OPTIONS,
    WIFI_CHANNELS,
    WIFI_COUNTRIES,
)
from ..models import (  # noqa: F401
    AuditLog,
    ClientProfile,
    Device,
    DeviceCommand,
    MobilePairingToken,
    NetworkClient,
    User,
    UserSession,
)
from ..security import (  # noqa: F401
    create_web_session_token,
    hash_password,
    verify_password,
    verify_user_password,
)
from ..schemas import SetupRequest  # noqa: F401
from ..services.audit import audit  # noqa: F401
from ..services.auth import settings, web_user_from_session  # noqa: F401
from ..services.client_registry import (  # noqa: F401
    client_response,
    effective_policy,
    validate_client_policy,
)
from ..services.commands import (  # noqa: F401
    ALLOWED_COMMANDS,
    build_command_payload_from_web_form,
    cleanup_device_command_history,
    command_history_entry,
    create_device_command,
    validate_command_request,
)
from ..services.config_transactions import (  # noqa: F401
    build_command_preview,
    ensure_preflight_valid,
)
from ..services.database_backups import (  # noqa: F401
    create_backup,
    default_backup_path,
)
from ..services.devices import (  # noqa: F401
    delete_device_permanently,
    device_supports,
    get_user_device_or_404,
    latest_device_telemetry,
)
from ..services.login_guard import (  # noqa: F401
    enforce_login_rate_limit,
    record_login_attempt,
)
from ..services.mobile_pairing import (  # noqa: F401
    create_pairing_token,
    get_user_pairing_token,
    pairing_response,
    pairing_status,
)
from ..services.operations import operational_notifications  # noqa: F401
from ..services.sessions import revoke_all_user_sessions  # noqa: F401
from ..services.setup import (  # noqa: F401
    complete_setup,
    get_public_server_url,
    is_setup_required,
)
from ..services.telemetry import (  # noqa: F401
    device_telemetry_history,
    normalize_clients_summary,
    normalize_maintenance_summary,
    normalize_network_summary,
    normalize_services_summary,
    normalize_system_summary,
    normalize_vpn_summary,
    normalize_wifi_summary,
    telemetry_alerts,
)
from .csrf import generate_csrf_token, verify_csrf_token  # noqa: F401


templates = Jinja2Templates(directory="backend/app/templates")
router = APIRouter()
BACKUP_DIRECTORY = Path("/backups")

DEVICE_SECTIONS = {
    "overview",
    "internet",
    "clients",
    "wifi",
    "rules",
    "vpn",
    "system",
    "management",
}


CAPABILITY_GROUPS = {
    "Agent": ("agent.",),
    "Telemetry": ("telemetry.",),
    "Wi-Fi": ("wifi.",),
    "Network": ("network.",),
    "VPN": ("vpn.",),
    "Clients & DHCP": ("clients.", "dhcp."),
    "Diagnostics": ("diagnostics.",),
    "System": ("system.",),
}


def format_timestamp(value: datetime | str | None) -> str:
    if value is None:
        return "нет данных"
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return value
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).strftime("%d.%m.%Y %H:%M:%S UTC")


def format_duration(value: int | None) -> str:
    if value is None:
        return "нет данных"
    days, remainder = divmod(int(value), 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, seconds = divmod(remainder, 60)
    parts: list[str] = []
    if days:
        parts.append(f"{days} д")
    if hours:
        parts.append(f"{hours} ч")
    if minutes:
        parts.append(f"{minutes} мин")
    if seconds or not parts:
        parts.append(f"{seconds} сек")
    return " ".join(parts)


def format_microseconds(value: int | float | None) -> str:
    if value is None:
        return "нет данных"
    microseconds = max(0, int(value))
    if microseconds < 1000:
        return f"{microseconds} мкс"
    milliseconds = microseconds / 1000
    if milliseconds < 1000:
        return f"{milliseconds:.0f} мс"
    return f"{milliseconds / 1000:.1f} сек"


def format_station_rate(value: int | float | str | None) -> str:
    if value is None or value == "":
        return "не передано"
    if isinstance(value, str):
        return value
    rate = float(value)
    if rate >= 1_000_000:
        return f"{rate / 1_000_000:.1f} Гбит/с"
    if rate >= 1_000:
        return f"{rate / 1_000:.1f} Мбит/с"
    return f"{rate:.0f} Кбит/с"


def format_size_kb(value: int | float | None) -> str:
    if value is None:
        return "нет данных"
    size = float(value)
    if size >= 1024 * 1024:
        return f"{size / 1024 / 1024:.1f} ГБ"
    if size >= 1024:
        return f"{size / 1024:.0f} МБ"
    return f"{size:.0f} КБ"


def format_bytes(value: int | float | None) -> str:
    if value is None:
        return "нет данных"
    size = float(value)
    units = ("Б", "КБ", "МБ", "ГБ", "ТБ")
    unit = units[0]
    for unit in units:
        if abs(size) < 1024 or unit == units[-1]:
            break
        size /= 1024
    return f"{size:.1f} {unit}" if unit != "Б" else f"{size:.0f} {unit}"


def percent(used: int | float | None, total: int | float | None) -> int:
    if not total:
        return 0
    return max(0, min(100, round(float(used or 0) / float(total) * 100)))


def format_device_status(value: str | None) -> str:
    return {
        "online": "В сети",
        "offline": "Нет связи",
        "provisioned": "Ожидает подключения",
        "disconnecting": "Отключается",
        "disabled": "Отключён",
    }.get(str(value or "").lower(), value or "Неизвестно")


templates.env.filters["timestamp"] = format_timestamp
templates.env.filters["duration"] = format_duration
templates.env.filters["microseconds"] = format_microseconds
templates.env.filters["station_rate"] = format_station_rate
templates.env.filters["size_kb"] = format_size_kb
templates.env.filters["bytes"] = format_bytes
templates.env.filters["status_label"] = format_device_status


def capability_summary(capabilities: dict[str, bool]) -> str:
    if not capabilities:
        return "нет данных"
    enabled = sum(1 for enabled in capabilities.values() if enabled)
    disabled = sum(1 for enabled in capabilities.values() if not enabled)
    return f"{enabled} enabled / {disabled} disabled"


def grouped_capabilities(
    capabilities: dict[str, bool], details: dict[str, dict[str, object]] | None = None
) -> list[dict[str, object]]:
    grouped: list[dict[str, object]] = []
    if not capabilities:
        return grouped
    remaining = dict(sorted(capabilities.items()))
    for title, prefixes in CAPABILITY_GROUPS.items():
        enabled_items = [
            name
            for name, enabled in remaining.items()
            if enabled and name.startswith(prefixes)
        ]
        disabled_names = [
            name
            for name, enabled in remaining.items()
            if not enabled and name.startswith(prefixes)
        ]
        disabled_items = [
            {
                "name": name,
                "reason": str(
                    (details or {}).get(name, {}).get("reason") or "недоступно"
                ),
            }
            for name in disabled_names
        ]
        if enabled_items or disabled_names:
            grouped.append(
                {
                    "title": title,
                    "enabled": enabled_items,
                    "disabled": disabled_items,
                }
            )
            for name in [*enabled_items, *disabled_names]:
                remaining.pop(name, None)
    if remaining:
        grouped.append(
            {
                "title": "Other",
                "enabled": [name for name, enabled in remaining.items() if enabled],
                "disabled": [
                    {
                        "name": name,
                        "reason": str(
                            (details or {}).get(name, {}).get("reason") or "недоступно"
                        ),
                    }
                    for name, enabled in remaining.items()
                    if not enabled
                ],
            }
        )
    return grouped


def capabilities_hint(capabilities: dict[str, bool]) -> str | None:
    if capabilities:
        return None
    return "Агент ещё не передал capabilities. Обновите или переустановите агент."


def require_web_csrf(
    session_token: str | None, csrf_token: str, config: Settings
) -> None:
    if not session_token or not verify_csrf_token(
        session_token, csrf_token, config.jwt_secret
    ):
        raise HTTPException(status_code=403, detail="Invalid CSRF token")


def request_uses_https(request: Request) -> bool:
    forwarded_proto = request.headers.get("x-forwarded-proto", "")
    scheme = forwarded_proto.split(",", 1)[0].strip() or request.url.scheme
    return scheme.lower() == "https"


__all__ = [name for name in globals() if not name.startswith("__")]
