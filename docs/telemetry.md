# Telemetry

`wrtmonitor` принимает telemetry от OpenWrt agent через:

```http
POST /api/v1/agent/telemetry
```

Актуальный snapshot доступен владельцу сервера через:

```http
GET /api/v1/devices/{device_id}/telemetry/latest
```

Ответ содержит:

- `device_id`;
- `created_at`;
- `age_seconds`;
- `is_stale` — `true`, если snapshot старше 5 минут;
- `source` — сейчас всегда `agent`;
- `telemetry` — последний payload или `null`, если данных ещё нет.
- `system`, `services`, `clients`, `wifi`, `network`, `vpn` — нормализованные блоки для интерфейсов.

OpenWrt agent собирает:

- `system`: uptime, load 1/5/15, память, hostname, kernel, conntrack, сервисы, часовой пояс, NTP и `ubus system info`;
- `board`: `ubus system board`;
- `network`: интерфейсы, IPv4 с длиной префикса и маской, IPv6, gateway, DNS, устройства и traffic;
- `wifi`: multi-radio snapshot, SSID, channel, country, htmode и параметры интерфейсов;
- `clients`: DHCP leases, neighbour table и, при наличии `nlbwmon`, RX/TX по MAC;
- `dhcp`: динамические и статические leases, реальные границы и срок аренды DHCP-пулов;
- `agent`: версия, update status, interval и capabilities.
- `vpn`: WireGuard-интерфейсы и peer, handshake/RX/TX, OpenVPN profiles и правила PBR без приватных ключей.

`schema_version=2` остаётся форматом telemetry; capability report в `v0.11.0` имеет версию 10. Сервер принимает как текущий компактный формат агента, так и прежний ответ `ubus`. Отсутствующие подсистемы возвращаются пустыми блоками и не ломают ingest. Блок `maintenance` содержит количество пакетов и обновлений, число cron-заданий, recovery mode и checksum подготовленной прошивки.

Retention: сервер хранит последние 100 telemetry snapshots на устройство. Старые snapshots удаляются после успешного ingest.

Реестр клиентов живёт отдельно от raw telemetry. Для каждого MAC сохраняются первая и последняя активность, имя, vendor и до 96 последних точек счётчиков.
