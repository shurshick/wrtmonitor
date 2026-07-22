# Telemetry

`wrtmonitor` принимает telemetry от OpenWrt agent через:

```http
POST /api/v1/agent/telemetry
```

Актуальный snapshot доступен владельцу сервера через:

```http
GET /api/v1/devices/{device_id}/telemetry/latest
```

История для живых графиков доступна через:

```http
GET /api/v1/devices/{device_id}/telemetry/history?range=24h
```

Диапазоны: `live` (2 часа), `24h`, `7d`, `30d`. Сервер сам уменьшает плотность длинных диапазонов и возвращает не более 360 точек. Скорость считается по разнице накопительных RX/TX-счётчиков; сброс счётчика не создаёт ложный всплеск.

Ответ содержит:

- `device_id`;
- `created_at`;
- `age_seconds`;
- `is_stale` — `true`, если snapshot старше 5 минут;
- `source` — сейчас всегда `agent`;
- `telemetry` — последний payload или `null`, если данных ещё нет.
- `system`, `services`, `clients`, `wifi`, `network`, `vpn` — нормализованные блоки для интерфейсов.
- `alerts` — предупреждения о потере связи, памяти и WAN.

OpenWrt agent собирает:

- `system`: uptime, load 1/5/15, память, hostname, kernel, conntrack, сервисы, часовой пояс, NTP и `ubus system info`;
- `board`: `ubus system board`;
- `network`: интерфейсы, IPv4 с длиной префикса и маской, IPv6, gateway, DNS, устройства и traffic;
- `wifi`: multi-radio snapshot, SSID, channel, country, htmode и параметры интерфейсов;
- `clients`: DHCP leases, neighbour table и, при наличии `nlbwmon`, RX/TX по MAC;
- `dhcp`: динамические и статические leases, реальные границы и срок аренды DHCP-пулов;
- `agent`: версия, update status, interval и capabilities.
- `vpn`: WireGuard-интерфейсы и peer, handshake/RX/TX, OpenVPN profiles и правила PBR без приватных ключей.

`schema_version=2` остаётся форматом telemetry; capability report в `v0.14.2` имеет версию 13. Сервер принимает как текущий компактный формат агента, так и прежний ответ `ubus`. Активные Wi-Fi-станции содержат SSID, диапазон, интерфейс и параметры сигнала. LAN передаёт реальные `ip6assign`, `ip6hint`, RA, DHCPv6 и NDP, а источник клиентского трафика сообщает отдельный статус `ready`, `query_failed` или `unavailable`. Отсутствующие подсистемы возвращаются пустыми блоками и не ломают ingest. Блок `maintenance` содержит количество и ограниченные списки пакетов/обновлений, число cron-заданий, recovery mode и checksum подготовленной прошивки. Объекты firewall содержат безопасные UCI section для адресного редактирования и удаления.

Retention разделён: последние 100 исходных JSON snapshots нужны для диагностики, а компактные метрики графиков хранятся 45 дней. Срок метрик задаётся `WRTMONITOR_TELEMETRY_METRIC_RETENTION_DAYS`.

Реестр клиентов живёт отдельно от raw telemetry. Для каждого MAC сохраняются первая активность, последнее наблюдение, последнее подтверждённое присутствие, имя, vendor и до 96 последних точек счётчиков.

## Присутствие клиентов

Статус клиента не определяется наличием записи в DHCP. Аренда может жить часами после отключения устройства, поэтому сервер использует три состояния:

- `online` — присутствие подтверждено активной Wi-Fi station, состоянием neighbour `REACHABLE`/`DELAY`/`PROBE` или ростом клиентских RX/TX-счётчиков;
- `recent` — устройство видели недавно, но активного подтверждения уже нет; сюда относится neighbour `STALE`;
- `offline` — подтверждение истекло либо neighbour явно вернул `FAILED`/`INCOMPLETE`.

`PERMANENT` и `NOARP` не считаются свидетельством активности: они описывают способ хранения neighbour-записи. Повторное чтение одной и той же `STALE`-записи не продлевает её срок.

Подтверждённый статус действует не менее 30 секунд и в обычном режиме равен трём интервалам агента. Состояние `recent` хранится не менее 5 минут и обычно равно десяти интервалам. Поэтому единичный пропущенный опрос не создаёт ложное отключение, а остановившийся агент не оставляет клиентов онлайн навсегда.

Latest telemetry и API клиентов возвращают `presence_state`, `presence_source`, `last_observed_at`, `last_confirmed_at` и `presence_expires_at`. Поле `online` сохранено для совместимости и равно `true` только для текущего подтверждённого состояния.
