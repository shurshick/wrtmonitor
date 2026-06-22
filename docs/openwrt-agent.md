# OpenWrt agent

`wrtmonitor-agent` регистрирует роутер, отправляет telemetry, получает команды с сервера и умеет безопасно обновлять сам себя с собственного сервера WrtMonitor.

## Требования

- OpenWrt с `opkg`;
- исходящий доступ роутера к серверу WrtMonitor;
- созданный администратор сервера;
- для HTTPS нужен `ca-bundle`.

Установщик сам подтягивает зависимости через `opkg`, если их не хватает:

- `curl`
- `jsonfilter`
- `uci`
- `ubus`
- `ca-bundle`
- `coreutils-sha256sum`

## Установка с собственного сервера

Рекомендуемый способ:

```sh
cd /tmp
BASE_URL='https://monitor.example.ru/downloads/openwrt'

wget -O wrtmonitor-agent "$BASE_URL/wrtmonitor-agent"
wget -O wrtmonitor.init "$BASE_URL/wrtmonitor.init"
wget -O install-openwrt.sh "$BASE_URL/install-openwrt.sh"
chmod 0755 wrtmonitor-agent wrtmonitor.init install-openwrt.sh

sh install-openwrt.sh \
  --server 'https://monitor.example.ru' \
  --admin-user 'admin@example.com' \
  --admin-password 'your-admin-password' \
  --name 'HomeRouter'
```

## Установка из GitHub Release

Если сервер еще не обновлен до нужной версии:

```sh
cd /tmp
wget -O wrtmonitor-agent.tar.gz \
  https://github.com/shurshick/wrtmonitor/releases/download/v0.1.1-rc8-router-management-core/wrtmonitor-openwrt-agent-v0.1.1-rc8.tar.gz
tar -xzf wrtmonitor-agent.tar.gz
sh install-openwrt.sh \
  --server 'https://monitor.example.ru' \
  --admin-user 'admin@example.com' \
  --admin-password 'your-admin-password' \
  --name 'HomeRouter'
```

## Проверка после установки

```sh
uci show wrtmonitor
/etc/init.d/wrtmonitor enabled
ps | grep wrtmonitor
wrtmonitor-agent version
wrtmonitor-agent capabilities --json
wrtmonitor-agent diagnostics --json
wrtmonitor-agent send-now
logread | grep wrtmonitor | tail -50
```

## Capabilities

Agent отдает список своих возможностей:

```sh
wrtmonitor-agent capabilities
wrtmonitor-agent capabilities --json
```

Этот блок попадает в latest telemetry как `agent.capabilities`. Сервер, Web UI и Android используют его для скрытия неподдерживаемых действий.

Если capabilities не удалось собрать, telemetry не должна падать: сервер переходит в read-only fallback.

## Diagnostics

Поддерживаются команды:

```sh
wrtmonitor-agent check-server
wrtmonitor-agent check-dns
wrtmonitor-agent check-route
wrtmonitor-agent check-wifi
wrtmonitor-agent check-dependencies
wrtmonitor-agent diagnostics
wrtmonitor-agent diagnostics --json
```

Проверки покрывают:

- доступность `/health`;
- DNS-резолвинг сервера;
- default route;
- наличие wireless-конфига и Wi-Fi telemetry;
- обязательные зависимости.

## Wi-Fi изменения и backup

Перед командами:

- `wifi.set_enabled`
- `wifi.set_ssid`
- `wifi.set_password`

agent создает backup:

```text
/etc/wrtmonitor/config-backups/wireless-YYYYMMDD-HHMMSS-<command_id>.bak
```

И metadata-файл:

```text
/etc/wrtmonitor/config-backups/wireless-YYYYMMDD-HHMMSS-<command_id>.meta
```

Список backup:

```sh
wrtmonitor-agent list-config-backups
```

Если backup не создался, Wi-Fi-команда завершается с `failed` до изменения конфигурации.

## Auto-update

Agent проверяет сервер по адресу:

```text
https://monitor.example.ru/downloads/openwrt/
```

Во время обновления agent:

1. скачивает `wrtmonitor-agent`, `wrtmonitor.init`, `install-openwrt.sh`, `agent-version.txt`, `SHA256SUMS.txt`;
2. проверяет `SHA-256`;
3. делает `sh -n` для shell-скриптов;
4. сохраняет backup предыдущей версии;
5. заменяет файлы;
6. при ошибке выполняет rollback.

## Ручное обновление

```sh
wrtmonitor-agent version
wrtmonitor-agent update
wrtmonitor-agent update --force
wrtmonitor-agent update --allow-downgrade
wrtmonitor-agent update-status
wrtmonitor-agent update-status --json
```

## Rollback

```sh
wrtmonitor-agent rollback
```

Backup хранится в:

```text
/etc/wrtmonitor/backup/
```

## Отключение автообновления

```sh
uci get wrtmonitor.main.auto_update
uci set wrtmonitor.main.auto_update='0'
uci commit wrtmonitor
```

Дополнительные параметры:

```sh
uci set wrtmonitor.main.update_interval_hours='6'
uci set wrtmonitor.main.update_channel='stable'
uci set wrtmonitor.main.allow_downgrade='0'
uci commit wrtmonitor
```

## Удаление агента

```sh
/etc/init.d/wrtmonitor stop 2>/dev/null || true
/etc/init.d/wrtmonitor disable 2>/dev/null || true
rm -f /usr/bin/wrtmonitor-agent
rm -f /etc/init.d/wrtmonitor
rm -f /etc/config/wrtmonitor
rm -rf /etc/wrtmonitor
```

## Troubleshooting

Проверка логов:

```sh
logread | grep wrtmonitor | tail -50
```

Типовые ситуации:

- `checksum mismatch`
  Обычно сервер раздает не те файлы или `SHA256SUMS.txt` устарел.
- `download failed`
  Нет доступа к серверу, DNS или HTTPS.
- `server unreachable`
  Проверьте `server_url`, DNS, шлюз и сертификаты.
- `rollback completed`
  Обновление сорвалось, agent вернул предыдущую рабочую версию.
- `backup failed`
  Перед Wi-Fi-командой не удалось создать backup `wireless`.
