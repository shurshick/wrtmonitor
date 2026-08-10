from __future__ import annotations

from typing import Any

from .telemetry_common import TELEMETRY_STALE_SECONDS, _safe_float, _safe_int
from .telemetry_network import normalize_network_summary
from .telemetry_wifi import normalize_wifi_summary


def _state(
    kind: str,
    label: str,
    detail: str,
    *,
    observed: bool = True,
) -> dict[str, Any]:
    return {"state": kind, "label": label, "detail": detail, "observed": observed}


def _thermal_health(
    payload: dict[str, Any],
) -> tuple[dict[str, Any], list[dict[str, str]]]:
    thermal = payload.get("thermal") or {}
    sensors = [item for item in thermal.get("sensors") or [] if isinstance(item, dict)]
    if not thermal.get("available") or not sensors:
        return _state(
            "unsupported",
            "Нет датчика",
            "Температура не поддерживается",
            observed=False,
        ), []
    hottest = max(sensors, key=lambda item: _safe_int(item.get("milli_celsius")))
    current = _safe_int(hottest.get("milli_celsius"))
    warning = _safe_int(hottest.get("warning_milli_celsius"))
    critical = _safe_int(hottest.get("critical_milli_celsius"))
    value = current / 1000
    alerts: list[dict[str, str]] = []
    if critical and current >= critical:
        alerts.append(
            {
                "level": "critical",
                "code": "temperature.critical",
                "message": f"Критическая температура: {value:.1f} °C",
            }
        )
        return _state("critical", "Перегрев", f"{value:.1f} °C"), alerts
    if warning and current >= warning:
        alerts.append(
            {
                "level": "warning",
                "code": "temperature.warning",
                "message": f"Высокая температура: {value:.1f} °C",
            }
        )
        return _state("warning", "Горячо", f"{value:.1f} °C"), alerts
    return _state("ok", "Норма", f"{value:.1f} °C"), alerts


def build_health_snapshot(
    payload: dict[str, Any] | None,
    age_seconds: int | None,
    *,
    agent: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not payload:
        unavailable = _state(
            "unknown", "Нет данных", "Telemetry ещё не получена", observed=False
        )
        return {
            "overall": "warning",
            "items": {
                name: dict(unavailable)
                for name in (
                    "agent",
                    "wan",
                    "dns",
                    "wifi",
                    "temperature",
                    "memory",
                    "storage",
                )
            },
            "alerts": [
                {
                    "level": "warning",
                    "code": "no_data",
                    "message": "Telemetry ещё не получена",
                }
            ],
        }

    alerts: list[dict[str, str]] = []
    stale = age_seconds is None or age_seconds > TELEMETRY_STALE_SECONDS
    if stale:
        alerts.append(
            {
                "level": "critical",
                "code": "stale",
                "message": "Связь с роутером потеряна",
            }
        )
    agent_item = _state(
        "critical" if stale else "ok",
        "Нет связи" if stale else "На связи",
        f"Последние данные {age_seconds} сек назад"
        if age_seconds is not None
        else "Время связи неизвестно",
    )
    if agent and agent.get("status") not in {None, "running", "online", "ok"}:
        agent_item = _state("warning", "Требует внимания", str(agent.get("status")))

    network = normalize_network_summary(payload)
    wan = next(
        (
            item
            for item in network.get("interfaces") or []
            if item.get("interface") == "wan"
        ),
        None,
    )
    if wan is None:
        wan_item = _state(
            "unsupported", "Не определён", "WAN-интерфейс не найден", observed=False
        )
    elif wan.get("up"):
        address = next(
            iter(wan.get("ipv4") or wan.get("ipv6") or []), "Адрес не назначен"
        )
        wan_item = _state("ok", "Подключён", str(address))
    else:
        wan_item = _state(
            "critical", "Нет подключения", str(wan.get("device") or "WAN")
        )
        alerts.append(
            {
                "level": "critical",
                "code": "wan",
                "message": "Интернет-соединение недоступно",
            }
        )

    dns_servers = list(wan.get("dns") or []) if wan else []
    services = (payload.get("system") or {}).get("services") or {}
    dnsmasq = str(services.get("dnsmasq") or "").lower()
    if dns_servers and dnsmasq in {"running", "active", "started"}:
        dns_item = _state("ok", "Работает", ", ".join(map(str, dns_servers[:2])))
    elif dnsmasq in {"stopped", "failed", "inactive"}:
        dns_item = _state("critical", "Служба остановлена", "dnsmasq")
        alerts.append(
            {
                "level": "critical",
                "code": "dns",
                "message": "DNS-служба роутера остановлена",
            }
        )
    elif dns_servers:
        dns_item = _state("ok", "Настроен", ", ".join(map(str, dns_servers[:2])))
    else:
        dns_item = _state(
            "unknown", "Не подтверждён", "DNS-серверы не получены", observed=False
        )

    wifi = normalize_wifi_summary(payload)
    radios = wifi.get("radios") or []
    enabled_radios = [
        radio for radio in radios if radio.get("up") and not radio.get("disabled")
    ]
    if wifi.get("available") is False:
        wifi_item = _state(
            "unsupported", "Нет радиомодуля", "Wi-Fi не поддерживается", observed=False
        )
    elif enabled_radios:
        wifi_item = _state(
            "ok",
            "Работает",
            f"{len(enabled_radios)} радиомодулей · {wifi.get('station_count') or 0} клиентов",
        )
    elif radios:
        wifi_item = _state("warning", "Выключен", "Все радиомодули отключены")
    else:
        wifi_item = _state(
            "unknown", "Нет данных", "Состояние Wi-Fi не получено", observed=False
        )

    system = payload.get("system") or {}
    memory = system.get("memory") or {}
    memory_total = _safe_int(memory.get("total_kb"))
    memory_available = _safe_int(memory.get("available_kb", memory.get("free_kb")))
    memory_percent = (
        100 * max(0, memory_total - memory_available) / memory_total
        if memory_total
        else None
    )
    if memory_percent is None:
        memory_item = _state(
            "unknown", "Нет данных", "Использование памяти не получено", observed=False
        )
    elif memory_percent >= 90:
        memory_item = _state(
            "critical", "Память заканчивается", f"Использовано {memory_percent:.0f}%"
        )
        alerts.append(
            {
                "level": "critical",
                "code": "memory",
                "message": f"Использовано {memory_percent:.0f}% оперативной памяти",
            }
        )
    elif memory_percent >= 80:
        memory_item = _state(
            "warning", "Высокое использование", f"Использовано {memory_percent:.0f}%"
        )
        alerts.append(
            {
                "level": "warning",
                "code": "memory",
                "message": f"Использовано {memory_percent:.0f}% оперативной памяти",
            }
        )
    else:
        memory_item = _state("ok", "Норма", f"Использовано {memory_percent:.0f}%")

    storage = payload.get("storage") or {}
    storage_total = _safe_int(storage.get("total_kb"))
    storage_available = _safe_int(storage.get("available_kb"))
    storage_percent = (
        100 * max(0, storage_total - storage_available) / storage_total
        if storage_total
        else None
    )
    if storage_percent is None:
        storage_item = _state(
            "unknown",
            "Нет данных",
            "Использование накопителя не получено",
            observed=False,
        )
    elif storage_percent >= 95:
        storage_item = _state(
            "critical", "Место заканчивается", f"Использовано {storage_percent:.0f}%"
        )
        alerts.append(
            {
                "level": "critical",
                "code": "storage",
                "message": f"Накопитель заполнен на {storage_percent:.0f}%",
            }
        )
    elif storage_percent >= 85:
        storage_item = _state(
            "warning", "Мало места", f"Использовано {storage_percent:.0f}%"
        )
        alerts.append(
            {
                "level": "warning",
                "code": "storage",
                "message": f"Накопитель заполнен на {storage_percent:.0f}%",
            }
        )
    else:
        storage_item = _state("ok", "Норма", f"Использовано {storage_percent:.0f}%")

    thermal_item, thermal_alerts = _thermal_health(payload)
    alerts.extend(thermal_alerts)
    cpu_count = max(
        1,
        _safe_int(system.get("cpu_count"))
        or _safe_int((payload.get("cpu") or {}).get("cores"))
        or 1,
    )
    load_1m = _safe_float(system.get("load_1m", system.get("load")))
    if load_1m / cpu_count >= 1.5:
        alerts.append(
            {
                "level": "warning",
                "code": "load.high",
                "message": "Высокая нагрузка на процессор держится последнюю минуту",
            }
        )

    items = {
        "agent": agent_item,
        "wan": wan_item,
        "dns": dns_item,
        "wifi": wifi_item,
        "temperature": thermal_item,
        "memory": memory_item,
        "storage": storage_item,
    }
    overall = (
        "critical"
        if any(item["state"] == "critical" for item in items.values())
        else "warning"
        if any(item["state"] == "warning" for item in items.values())
        else "ok"
    )
    return {"overall": overall, "items": items, "alerts": alerts}


__all__ = ["build_health_snapshot"]
