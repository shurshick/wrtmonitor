# API WrtMonitor

## Авторизация

Access-token владельца действует 15 минут. Refresh-token управляется серверной сессией и ротируется при каждом использовании.

- `POST /api/v1/auth/login` — создать access/refresh пару;
- `POST /api/v1/auth/refresh` — атомарно заменить refresh-token;
- `POST /api/v1/auth/logout` — отозвать текущую refresh-сессию;
- `GET /api/v1/auth/sessions` — список сессий владельца;
- `DELETE /api/v1/auth/sessions/{id}` — отозвать сессию;
- `POST /api/v1/auth/change-password` — сменить пароль и отозвать все refresh-сессии;
- `GET /api/v1/operations/notifications` — эксплуатационные уведомления.
- `GET /api/v1/operations/events` — постоянный журнал событий с фильтрами и пагинацией;
- `POST /api/v1/operations/events/{id}/acknowledge` — подтвердить событие;
- `POST /api/v1/operations/events/{id}/snooze` — отложить событие;
- `GET|POST /api/v1/operations/notification-rules` — правила доставки;
- `PUT|DELETE /api/v1/operations/notification-rules/{id}` — изменение и удаление правила;
- `GET|POST /api/v1/operations/automation-rules` — безопасные сценарии;
- `PUT|DELETE /api/v1/operations/automation-rules/{id}` — изменение и удаление сценария;
- `GET /api/v1/operations/automation/templates` — готовые сценарии;
- `GET /api/v1/operations/automation-runs` — фактическая история запусков.

- `POST /api/v1/auth/login` возвращает `access_token`, `refresh_token` и `expires_in`.
- `POST /api/v1/auth/refresh` принимает `refresh_token` и выдаёт новую пару токенов.

Access token используется клиентами владельца. Device token агента не участвует в refresh flow.

## Mobile pairing

Android подключается только к WrtMonitor Server. Pairing не регистрирует OpenWrt-агент и не открывает прямой доступ к роутеру.

- `POST /api/v1/mobile-pairing/tokens` — создать одноразовый token владельца;
- `GET /api/v1/mobile-pairing/tokens/{id}` — получить состояние;
- `DELETE /api/v1/mobile-pairing/tokens/{id}` — отозвать неиспользованный token;
- `POST /api/v1/mobile-pairing/exchange` — однократно обменять token на access/refresh-сессию;
- `GET /api/v1/auth/sessions?client_type=mobile_pairing&active_only=true` — список активных мобильных сессий;
- `DELETE /api/v1/auth/sessions/{id}` — отозвать выбранную мобильную сессию.

Создание, чтение и отзыв pairing token требуют bearer-сессию владельца. Exchange не требует авторизации, но защищён одноразовостью, 10-минутным TTL и PostgreSQL rate limiting.

Формат QR v1 — компактный JSON:

```json
{"type":"wrtmonitor-mobile-setup","version":1,"server_url":"https://monitor.example.ru","pairing_token":"ONE_TIME_TOKEN"}
```

В базе сохраняется только SHA-256 hash. Исходный token возвращается один раз при создании и не попадает в аудит. Публичный URL берётся только из `WRTMONITOR_PUBLIC_SERVER_URL` или значения первичной настройки, поэтому заголовок reverse proxy не может подменить адрес QR.

Отзыв «всех сессий кроме текущей» не реализован намеренно: stateless access token не содержит идентификатор refresh-сессии, поэтому сервер не может надёжно определить «текущую». Доступен точечный отзыв каждой сессии.

## Основные backend endpoints

Сохраняются и поддерживаются:

- `GET /api/v1/devices`
- `POST /api/v1/devices/provision`
- `GET /api/v1/devices/{device_id}/commands`
- `POST /api/v1/devices/{device_id}/commands`
- `POST /api/v1/devices/{device_id}/disconnect`
- `DELETE /api/v1/devices/{device_id}` — безвозвратно удалить роутер и связанные данные
- `GET /api/v1/devices/{device_id}/telemetry/latest`
- `GET /api/v1/devices/{device_id}/telemetry/history?range=live|24h|7d|30d`
- `GET /api/v1/devices/{device_id}/events` — SSE telemetry и статусов команд для авторизованного Web/Android-клиента
- `GET /api/v1/devices/{device_id}/agent`
- `GET /api/v1/devices/{device_id}/clients`
- `PUT|PATCH /api/v1/devices/{device_id}/clients/{client_id}`
- `POST /api/v1/devices/{device_id}/clients/{client_id}/apply-policy`
- `GET /api/v1/devices/{device_id}/clients/{client_id}/traffic`
- `GET|POST /api/v1/devices/{device_id}/client-profiles`
- `PUT|DELETE /api/v1/devices/{device_id}/client-profiles/{profile_id}`
- `POST /api/v1/agent/register`
- `POST /api/v1/agent/token/rotate`
- `POST /api/v1/agent/token/confirm` — завершить ротацию после записи UCI;
- `POST /api/v1/agent/token/rollback` — аварийный откат по одноразовому rollback nonce при ошибке записи UCI
- `GET /api/v1/agent/commands?wait=0..30` — короткий polling или ожидающий long-poll
- `POST /api/v1/agent/commands/{command_id}/result`
- `GET /api/v1/meta/contracts`

## Web-терминал

- `WS /api/v1/devices/{device_id}/terminal/ws` — браузерная owner-сессия, кадры `input`, `resize`, `close`;
- `GET /api/v1/agent/terminal/sessions/{session_id}/down` — конечный long-poll входных кадров для агента;
- `PUT /api/v1/agent/terminal/sessions/{session_id}/up` — поток вывода PTY;
- `POST /api/v1/agent/terminal/sessions/{session_id}/status` — состояние `connecting`, `connected`, `closed` или `failed`.

Browser WebSocket принимает только авторизованную cookie и same-origin запрос. Agent endpoints требуют device token того же роутера, которому принадлежит UUID сессии.

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
- `hardware`
- `alerts`

Нормализованные блоки предназначены для Web UI и Android. Исходный `telemetry` JSON сохраняется для диагностики.

`hardware` содержит observed identity и CPU, необязательное дополнение `catalog`, список датчиков и способ сопоставления. `catalog` не является источником текущей температуры или частоты.

`GET /api/v1/devices/{device_id}/telemetry/history?range=24h` возвращает подготовленный для графика ряд: время, RX/TX bit/s, накопительные байты, load 1m, процент занятой памяти и число клиентов. Поддерживаются `live`, `24h`, `7d`, `30d`; длинные диапазоны уменьшаются на сервере до 360 точек.

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
  "confirmed": true,
  "idempotency_key": "android-550e8400-e29b-41d4-a716-446655440000"
}
```

`idempotency_key` необязателен для старых клиентов, но обязателен для новых интеграций. Повторный запрос с тем же ключом и типом команды возвращает существующую команду; использование ключа для другого типа даёт `409`.

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

### Управляющие команды

Расширенный Wi-Fi: `wifi.set_radio`, `wifi.add_ssid`, `wifi.update_ssid`, `wifi.delete_ssid`, `wifi.set_schedule`, `wifi.set_mesh`. Сервер валидирует radio/iface, режим защиты, длину ключа, channel/htmode/txpower, дни и время расписания до постановки команды в очередь.

- `wifi.set_enabled`, `wifi.set_ssid`, `wifi.set_password`, `wifi.set_channel`, `wifi.set_country`
- `network.interfaces`, `network.interface_restart`, `network.restart`
- `network.set_wan`, `network.set_lan`, `network.set_segment`, `network.delete_segment`
- `network.set_vlan`, `network.delete_vlan`
- `dhcp.set_lease`, `dhcp.delete_lease`, `dhcp.set_pool`, `dns.set_servers`
- `firewall.set_port_forward`, `firewall.delete_port_forward`, `client.set_blocked`, `client.set_policy`
- `qos.set_sqm`
- `wifi.set_guest`
- `system.set_hostname`, `system.restart_service`, `system.set_timezone`, `system.set_ntp`, `router.reboot`
- `agent.update`, `agent.rollback`, `agent.set_auto_update`, `agent.set_interval`, `agent.rotate_token`, `agent.disconnect`
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

## Служебные endpoints

- `GET /live` — процесс отвечает, PostgreSQL не проверяется;
- `GET /ready` — приложение и PostgreSQL готовы принимать трафик;
- `GET /health` — совместимый healthcheck с проверкой PostgreSQL;
- `GET /metrics` — Prometheus text format, только при `WRTMONITOR_ENABLE_METRICS=true`.

Каждый HTTP-ответ содержит `X-Request-ID` и `Server-Timing`. Клиентский `X-Request-ID` принимается только в безопасном формате длиной до 128 символов.
