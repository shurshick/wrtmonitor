# API WrtMonitor

## Авторизация

- `POST /api/v1/auth/login` возвращает `access_token`, `refresh_token` и `expires_in`.
- `POST /api/v1/auth/refresh` принимает `refresh_token` и выдаёт новую пару токенов.

Access token используется клиентами владельца. Device token агента не участвует в refresh flow.

## Основные backend endpoints

Сохраняются и поддерживаются:

- `GET /api/v1/devices`
- `POST /api/v1/devices/provision`
- `GET /api/v1/devices/{device_id}/commands`
- `POST /api/v1/devices/{device_id}/commands`
- `POST /api/v1/devices/{device_id}/disconnect`
- `DELETE /api/v1/devices/{device_id}` — безвозвратно удалить роутер и связанные данные
- `GET /api/v1/devices/{device_id}/telemetry/latest`
- `GET /api/v1/devices/{device_id}/agent`
- `GET /api/v1/devices/{device_id}/clients`
- `PUT|PATCH /api/v1/devices/{device_id}/clients/{client_id}`
- `POST /api/v1/devices/{device_id}/clients/{client_id}/apply-policy`
- `GET /api/v1/devices/{device_id}/clients/{client_id}/traffic`
- `GET|POST /api/v1/devices/{device_id}/client-profiles`
- `PUT|DELETE /api/v1/devices/{device_id}/client-profiles/{profile_id}`
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
- `clients`
- `system`
- `services`

Нормализованные блоки предназначены для Web UI и Android. Исходный `telemetry` JSON сохраняется для диагностики.

## Agent status

`GET /api/v1/devices/{device_id}/agent`

Пример:

```json
{
  "version": "0.6.0",
  "status": "running",
  "auto_update_enabled": true,
  "telemetry_interval_seconds": 60,
  "last_update_status": "success",
  "last_update_error": "",
  "rollback_available": true,
  "capabilities": {
    "wifi.set_password": true,
    "network.write": false
  }
}
```

`GET /health/config` дополнительно возвращает технические признаки текущего сервера, включая:

- `version`
- `openwrt_downloads_enabled`
- `openwrt_downloads_path`
- `access_model`

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

Для изменения интервала telemetry:

```json
{
  "command_type": "agent.set_interval",
  "payload": {
    "interval_seconds": 15
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
- `level_4_disruptive`

### Предварительная проверка конфигурации

```http
POST /api/v1/devices/{device_id}/commands/preview
Authorization: Bearer <access_token>
Content-Type: application/json
```

Тело совпадает с созданием команды. Ответ содержит `changes`, `warnings`, `errors`, `can_apply`, список UCI-конфигураций и timeout автоматического rollback.

### Управляющие команды v0.6.0

Расширенный Wi-Fi: `wifi.set_radio`, `wifi.add_ssid`, `wifi.update_ssid`, `wifi.delete_ssid`, `wifi.set_schedule`, `wifi.set_mesh`. Сервер валидирует radio/iface, режим защиты, длину ключа, channel/htmode/txpower, дни и время расписания до постановки команды в очередь.

- `wifi.set_enabled`, `wifi.set_ssid`, `wifi.set_password`, `wifi.set_channel`, `wifi.set_country`
- `network.interfaces`, `network.interface_restart`, `network.restart`
- `network.set_wan`, `network.set_lan`
- `dhcp.set_lease`, `dhcp.delete_lease`, `dhcp.set_pool`, `dns.set_servers`
- `firewall.set_port_forward`, `firewall.delete_port_forward`, `client.set_blocked`, `client.set_policy`
- `qos.set_sqm`
- `wifi.set_guest`
- `system.set_hostname`, `system.restart_service`, `system.set_timezone`, `system.set_ntp`, `router.reboot`
- `agent.update`, `agent.rollback`, `agent.set_auto_update`, `agent.set_interval`, `agent.disconnect`
- `diagnostics.run`

`client.set_policy` принимает MAC, признак блокировки, расписание и приоритет. `qos.set_sqm` задаёт общие download/upload в Кбит/с для выбранного WAN-интерфейса. Точный per-client shaping в `v0.5.0` не обещается.

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
