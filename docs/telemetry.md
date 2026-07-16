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
- `system`, `services`, `clients`, `wifi`, `network` — нормализованные блоки для интерфейсов.

OpenWrt agent собирает:

- `system`: uptime, load 1/5/15, память, hostname, kernel, conntrack, сервисы и `ubus system info`;
- `board`: `ubus system board`;
- `network`: интерфейсы, адреса, gateway, DNS, устройства и traffic;
- `wifi`: multi-radio snapshot, SSID, channel, country, htmode и параметры интерфейсов;
- `clients`: DHCP leases и neighbour table;
- `dhcp`: динамические и статические leases;
- `agent`: версия, update status, interval и capabilities.

`schema_version=2` используется в ветке `v0.2.0-rc2`. Отсутствующие подсистемы возвращаются пустыми блоками и не ломают ingest.

Retention: сервер хранит последние 100 telemetry snapshots на устройство. Старые snapshots удаляются после успешного ingest.
