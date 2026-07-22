# OpenWrt agent

`wrtmonitor-agent` регистрирует роутер, отправляет telemetry, получает команды с сервера и умеет обновлять сам себя.

Агент использует модульную структуру:

```text
wrtmonitor-agent
lib/common.sh
lib/status.sh
lib/update.sh
lib/telemetry.sh
lib/capabilities.sh
lib/diagnostics.sh
lib/transactions.sh
lib/commands.sh
lib/api.sh
```

Версия `0.14.2` использует capability schema 13, поддерживает `apk` и `opkg`, передаёт реальные параметры IPv6 LAN и устойчиво получает счётчики клиентов из `nlbwmon`. После установки `nlbwmon` агент включает и запускает службу автоматически. Обновление с `0.14.1` выполняется обычной кнопкой; переустановка не нужна.

## Требования

- OpenWrt 25.12+ с `apk` или предыдущая версия с `opkg`;
- исходящий доступ роутера к серверу WrtMonitor;
- созданный администратор сервера;
- для HTTPS нужен `ca-bundle`.

Installer определяет пакетный менеджер и сам подтягивает зависимости через `apk` или `opkg`, если их не хватает:

- `curl`
- `jsonfilter`
- `uci`
- `ubus`
- `ca-bundle`
- `coreutils-sha256sum`
- `coreutils-base64`

Для расширенных функций installer пытается установить `nlbwmon`, `wireguard-tools`, `openvpn-openssl` и `pbr`. Это опциональные зависимости: если пакета нет в feed конкретной сборки OpenWrt, агент продолжит работу, а соответствующая capability будет выключена с указанием причины.

По умолчанию агент отправляет telemetry и опрашивает команды раз в `60` секунд. Интервал можно менять из Web UI и Android, минимальное значение `5` секунд.

## Безопасное применение настроек

Перед изменением Wi-Fi, сети, DHCP, DNS, firewall или системной UCI-конфигурации агент создаёт точечную резервную копию. Для сетевых команд после применения запускается проверка связи с сервером. Если связь не восстановилась за 90 секунд, агент возвращает прежние файлы и перезапускает соответствующие сервисы. Подробности: [safe-configuration.md](safe-configuration.md).

## Установка с уже развернутого сервера

Рекомендуемый вариант:

```sh
cd /tmp
wget -O install-openwrt.sh \
  https://monitor.example.ru/downloads/openwrt/install-openwrt.sh
chmod 0755 install-openwrt.sh

sh install-openwrt.sh \
  --server 'https://monitor.example.ru' \
  --admin-user 'admin@example.com' \
  --admin-password 'your-admin-password' \
  --name 'HomeRouter'
```

Installer сам скачает:

- `openwrt-agent-files.txt`
- `SHA256SUMS.txt`
- `wrtmonitor-agent`
- `wrtmonitor.init`
- `install-openwrt.sh`
- `agent-version.txt`
- `lib/*.sh`

## Установка из GitHub Release

Если сервер ещё не обновлён до нужной версии:

```sh
cd /tmp
wget -O wrtmonitor-agent.tar.gz \
  https://github.com/shurshick/wrtmonitor/releases/download/v0.14.2/wrtmonitor-openwrt-agent-v0.14.2.tar.gz
tar -xzf wrtmonitor-agent.tar.gz
sh install-openwrt.sh \
  --server 'https://monitor.example.ru' \
  --admin-user 'admin@example.com' \
  --admin-password 'your-admin-password' \
  --name 'HomeRouter'
```

## Clean reinstall

Clean reinstall нужен только при повреждённой или очень старой установке:

```sh
cd /tmp
wget -O install-openwrt.sh \
  https://monitor.example.ru/downloads/openwrt/install-openwrt.sh
chmod 0755 install-openwrt.sh

sh install-openwrt.sh --clean \
  --server 'https://monitor.example.ru' \
  --admin-user 'admin@example.com' \
  --admin-password 'your-admin-password' \
  --name 'HomeRouter'
```

`--clean` удаляет старые:

- `/usr/bin/wrtmonitor-agent`
- `/usr/lib/wrtmonitor`
- `/etc/init.d/wrtmonitor`

При этом `/etc/config/wrtmonitor` сохраняется, если отдельно не передан `--remove-config`.

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

## Обновление агента

Ручная проверка и обновление:

```sh
wrtmonitor-agent version
wrtmonitor-agent update
wrtmonitor-agent update --force
wrtmonitor-agent update --allow-downgrade
wrtmonitor-agent update-status
wrtmonitor-agent update-status --json
```

Во время обновления агент:

1. скачивает `openwrt-agent-files.txt`;
2. скачивает все файлы из manifest;
3. проверяет `SHA256SUMS.txt`;
4. выполняет `sh -n` для `wrtmonitor-agent`, `wrtmonitor.init`, `install-openwrt.sh`, `lib/*.sh`;
5. сохраняет backup;
6. заменяет файлы;
7. при ошибке выполняет rollback.

## Rollback

```sh
wrtmonitor-agent rollback
```

Backup хранится в:

```text
/etc/wrtmonitor/backup/
```

## Capabilities

```sh
wrtmonitor-agent capabilities
wrtmonitor-agent capabilities --json
```

Этот блок попадает в latest telemetry как `agent.capabilities`. Сервер, Web UI и Android используют его для показа только поддерживаемых действий.

## Diagnostics

```sh
wrtmonitor-agent check-server
wrtmonitor-agent check-dns
wrtmonitor-agent check-route
wrtmonitor-agent check-wifi
wrtmonitor-agent check-dependencies
wrtmonitor-agent diagnostics
wrtmonitor-agent diagnostics --json
```

## Обслуживание роутера

Команды `v0.14.2` выполняются только через авторизованный сервер и показываются в интерфейсах по реальным capabilities роутера:

- обновление каталога, установка и удаление пакетов через `apk` или `opkg`;
- создание и восстановление штатного backup OpenWrt;
- загрузка и проверка sysupgrade-образа по HTTPS, SHA-256, модели, свободному месту и `sysupgrade -T`;
- чтение `logread`, отправка ограниченного набора сигналов процессам и замена root crontab;
- диагностический архив из board/system/network, журнала, процессов, дисков, пакетов и capabilities;
- recovery mode, в котором изменяющие команды блокируются до явного отключения режима.

Агент запрещает удалять критические пакеты OpenWrt. Конфигурация, токены, ключи Wi-Fi и VPN в диагностический архив не включаются. Backup и диагностический архив передаются серверу как результат команды и скачиваются владельцем через Web UI.

## Wi-Fi и backup

Агент поддерживает несколько `wifi-iface` на каждом `wifi-device`, настройку radio, расписание, 802.11r/k/v и Mesh 802.11s. Возможности публикуются динамически: `wifi.mesh` и `wifi.roaming` включаются только при наличии подходящего `wpad`/`hostapd` и режима mesh в `iw list`.

Расписание хранится в UCI `wrtmonitor` и проверяется в каждом цикле агента. Минимальная точность равна настроенному интервалу telemetry (не менее 5 секунд); отдельные записи cron не создаются.

Перед командами:

- `wifi.set_enabled`
- `wifi.set_ssid`
- `wifi.set_password`
- `wifi.set_channel`
- `wifi.set_country`

агент создаёт backup:

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

Для команд `system.set_hostname`, `dhcp.set_lease` и `dhcp.delete_lease` аналогично создаются backup файлов `system` и `dhcp`. Перезапуск сети и сервисов не меняет UCI-конфигурацию.

## Отключение автообновления

```sh
uci get wrtmonitor.main.auto_update
uci set wrtmonitor.main.auto_update='0'
uci commit wrtmonitor
```

## Интервал telemetry

Посмотреть текущее значение:

```sh
uci get wrtmonitor.main.interval
wrtmonitor-agent debug | grep '^interval='
```

Изменить вручную:

```sh
uci set wrtmonitor.main.interval='15'
uci commit wrtmonitor
/etc/init.d/wrtmonitor restart
```

Минимально допустимое значение: `5` секунд.

## Удаление агента

Оставить конфиг:

```sh
/etc/init.d/wrtmonitor stop 2>/dev/null || true
/etc/init.d/wrtmonitor disable 2>/dev/null || true
rm -f /usr/bin/wrtmonitor-agent
rm -f /etc/init.d/wrtmonitor
rm -rf /usr/lib/wrtmonitor
rm -rf /etc/wrtmonitor
```

Удалить агент вместе с конфигом:

```sh
/etc/init.d/wrtmonitor stop 2>/dev/null || true
/etc/init.d/wrtmonitor disable 2>/dev/null || true
rm -f /usr/bin/wrtmonitor-agent
rm -f /etc/init.d/wrtmonitor
rm -f /etc/config/wrtmonitor
rm -rf /usr/lib/wrtmonitor
rm -rf /etc/wrtmonitor
```

## Troubleshooting

```sh
logread | grep wrtmonitor | tail -50
```

Типовые ситуации:

- `checksum mismatch` — сервер раздаёт не те файлы или `SHA256SUMS.txt` устарел;
- `download failed` — нет доступа к серверу, DNS или HTTPS;
- `server unreachable` — проверьте `server_url`, DNS, шлюз и сертификаты;
- `rollback completed` — обновление сорвалось, агент вернул предыдущую рабочую версию;
- `backup failed` — перед Wi-Fi-командой не удалось создать backup `wireless`.
