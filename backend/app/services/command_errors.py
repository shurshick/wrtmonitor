from __future__ import annotations

from typing import Any


ERROR_TITLES_RU = {
    "resource_unavailable": "Нужный компонент недоступен",
    "invalid_request": "Параметры команды не приняты",
    "temporary_failure": "Временная ошибка на роутере",
    "safety_check_failed": "Проверка безопасности не пройдена",
    "operation_blocked": "Операция заблокирована",
    "post_condition_failed": "Роутер не подтвердил изменение",
    "unsupported_command": "Команда не поддерживается агентом",
    "command_failed": "Команда не выполнена",
}


def public_command_error(result: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(result, dict):
        return None
    detail = result.get("error_detail")
    if isinstance(detail, dict):
        code = str(detail.get("code") or "command_failed")
        technical = str(detail.get("message") or result.get("error") or "")
        return {
            "code": code,
            "title": ERROR_TITLES_RU.get(code, ERROR_TITLES_RU["command_failed"]),
            "message": technical,
            "retryable": bool(detail.get("retryable")),
        }
    if result.get("error"):
        return {
            "code": "command_failed",
            "title": ERROR_TITLES_RU["command_failed"],
            "message": str(result["error"]),
            "retryable": False,
        }
    return None
