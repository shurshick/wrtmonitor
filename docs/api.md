# API WrtMonitor

## Основные backend endpoints

Сохраняются и поддерживаются:

- `GET /api/v1/devices`
- `POST /api/v1/devices/provision`
- `GET /api/v1/devices/{device_id}/commands`
- `POST /api/v1/devices/{device_id}/commands`
- `POST /api/v1/devices/{device_id}/disconnect`
- `POST /api/v1/devices/{device_id}/archive`
- `GET /api/v1/devices/{device_id}/telemetry/latest`
- `GET /api/v1/devices/{device_id}/agent`
- `POST /api/v1/agent/register`
- `GET /api/v1/agent/commands`
- `POST /api/v1/agent/commands/{command_id}/result`

## Latest telemetry

`GET /api/v1/devices/{device_id}/telemetry/latest`

Возвращает:

- `created_at`
- `age_seconds`
- `is_stale`
- `source`
- `telemetry`
- `agent`
- `wifi`
- `network`

Нормализованные блоки `agent`, `wifi`, `network` предназначены для Web UI и Android. Старый `telemetry` JSON сохраняется для совместимости.

## Agent status

`GET /api/v1/devices/{device_id}/agent`

Пример:

```json
{
  "version": "0.1.1-rc8",
  "status": "running",
  "auto_update_enabled": true,
  "last_update_status": "success",
  "last_update_error": "",
  "rollback_available": true,
  "capabilities": {
    "wifi.set_password": true,
    "network.write": false
  }
}
```

## Создание команд

`POST /api/v1/devices/{device_id}/commands`

Body:

```json
{
  "command_type": "wifi.set_ssid",
  "payload": {
    "ssid": "HomeWiFi",
    "iface": "@wifi-iface[0]"
  },
  "confirmed": true
}
```

### Проверки backend

При создании команды backend проверяет:

1. команда есть в `COMMAND_REGISTRY`;
2. payload валиден;
3. capability доступен, если у устройства уже есть latest capabilities;
4. для risky-команд присутствует `confirmed=true`.

### Risk levels

- `level_1_readonly`
- `level_2_safe_action`
- `level_3_reversible_config`

### Secret masking

В списке команд и истории маскируются:

- `password`
- `wifi_password`
- `key`
- другие секретные поля из metadata команды

## Diagnostics

Поддерживается команда:

```json
{
  "command_type": "diagnostics.run",
  "payload": {
    "checks": ["server", "dns", "route", "wifi", "dependencies"]
  },
  "confirmed": true
}
```

`checks` можно опустить: тогда agent выполнит полный набор проверок.
