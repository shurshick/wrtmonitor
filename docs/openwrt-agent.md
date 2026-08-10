# OpenWrt agent

`wrtmonitor-agent` регистрирует роутер, отправляет telemetry, получает команды с сервера и умеет обновлять сам себя.

Начиная с `0.37.0` агент отдельно собирает аппаратную идентичность: Device Tree model/compatible, OpenWrt target, архитектуру, `cpufreq`, все `thermal_zone` и `hwmon` датчики. Абсолютные пути датчиков серверу не передаются; используются стабильный идентификатор, subsystem, type и label.

Агент использует модульную структуру:

```text
wrtmonitor-agent
lib/common.sh
lib/dependencies.sh
lib/status.sh
lib/update.sh
lib/telemetry.sh
lib/capabilities.sh
lib/diagnostics.sh
lib/transactions.sh
lib/idempotency.sh
lib/verification.sh
lib/commands.sh
lib/api.sh
```

Актуальный агент использует capability schema 16 и единый манифест обязательных runtime-зависимостей. Installer и обновление применяют этот манифест автоматически. Каждый payload-файл проверяется по SHA-256, а detached-манифест отдельно проверяется по встроенному Ed25519 public key.

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
- `ip-full`
- `iw`
- `iwinfo`
- `ca-bundle`
- `coreutils-sha256sum`
- `coreutils-base64`
- `openssl-util`
- `tar`
- `gzip`
- `base-files` с `sysupgrade`
- `nlbwmon`
- `ethtool`
- `script-utils` для PTY Web-терминала

`nlbwmon` обязателен для клиентских счётчиков. Агент проверяет его UCI-конфигурацию, добавляет сеть `lan`, включает автозапуск, запускает службу и проверяет локальный запрос `nlbw`. При остановке службы или недоступном сокете следующая telemetry выполняет автоматический перезапуск.

`wireguard-tools`, `openvpn-openssl` и `pbr` остаются опциональными: если пакета нет в feed конкретной сборки OpenWrt, соответствующая capability выключается с указанием причины.

По умолчанию агент отправляет telemetry и опрашивает команды раз в `60` секунд. Интервал можно менять из Web UI и Android, минимальное значение `5` секунд.

## Web-терминал

Раздел **Терминал** не открывает SSH-порт роутера. Сервер создаёт отдельную сессию, агент получает её как обычную авторизованную команду и запускает `/bin/ash -i` через `script` в PTY. Ввод, вывод и resize передаются исходящими HTTPS-запросами агента.

Installer и автообновление ставят `script-utils` автоматически. Проверка зависимости:

```sh
command -v script
wrtmonitor-agent capabilities --json | jsonfilter -e '@["agent.ssh_session"]'
```

При кратком обрыве агент повторно подключает потоки ввода и вывода. Закрытие вкладки завершает сессию; без активности сервер закроет её через 30 минут.

Терминал не использует период telemetry. После открытия PTY агент держит отдельный long-poll ввода и отправляет вывод конечными HTTPS-порциями. Сервер проверяет новый вывод примерно каждые `120` мс, агент проверяет кадры long-poll примерно каждые `150` мс; при отсутствии данных запрос удерживается до `20` секунд как heartbeat. Обычная задержка определяется сетью и составляет доли секунды, а не настроенные `5–60` секунд telemetry.

Команда `agent.ssh_session` считается успешной только после готовности PTY и обоих направлений транспорта. Если одно из них не поднялось, журнал операций показывает конкретную ошибку или `terminal startup readiness timeout`.

## Безопасное применение настроек

Перед изменением Wi-Fi, сети, DHCP, DNS, firewall или системной UCI-конфигурации агент создаёт точечную резервную копию. Для сетевых команд после применения запускается проверка связи с сервером. Если связь не восстановилась за 90 секунд, агент возвращает прежние файлы и перезапускает соответствующие сервисы. Подробности: [safe-configuration.md](safe-configuration.md).

Модули SMB, NFS, FTP, DLNA, USB-печати, накопителей и LTE/USB-модемов устанавливаются через Web UI или Android. Агент использует фиксированный список пакетов для выбранного модуля, сам обновляет каталог apk/opkg и проверяет результат установки. Аппаратные модули показываются только после обнаружения устройства либо если соответствующий пакет уже установлен.

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
- `SHA256SUMS.sig`
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
  https://github.com/shurshick/wrtmonitor/releases/latest/download/wrtmonitor-openwrt-agent-v<версия>.tar.gz
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

При этом `/etc/config/wrtmonitor` сохраняется, если отдельно не передан `--remove-config`. Параметры интервала и автообновления также сохраняются, но `server_url`, `device_id`, token и имя всегда заменяются результатом новой регистрации. Поэтому оставшийся конфиг больше не может привязать новый объект БД к старому удалённому роутеру.

Installer считает установку успешной только после принятой сервером первой telemetry и успешного запуска службы. В конце нормальной установки выводятся строки:

```text
Initial telemetry accepted by WrtMonitor server
wrtmonitor agent <версия> installed and running
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
3. проверяет Ed25519-подпись `SHA256SUMS.sig` встроенным public key;
4. проверяет SHA-256 каждого файла из `SHA256SUMS.txt`;
5. выполняет `sh -n` для `wrtmonitor-agent`, `wrtmonitor.init`, `install-openwrt.sh`, `lib/*.sh`;
6. сохраняет backup;
7. заменяет файлы;
8. при ошибке выполняет rollback;
9. запускает `ensure-dependencies` по манифесту новой версии и при ошибке также выполняет rollback.

При включённом автообновлении сервер ставит `agent.update` в очередь сразу после telemetry от устаревшей версии. Это основной путь обновления. Дополнительно агент раз в час самостоятельно проверяет файлы на своём сервере. После успешного обновления по команде daemon немедленно передаёт управление новой версии без ожидания следующего цикла.

## Связь с сервером

Агент версии `0.32.0` использует long-poll команд до 25 секунд. Новая команда будит запрос сразу после фиксации в БД. Интервал telemetry настраивается отдельно и не меняется из-за long-poll.

При ошибке сети повторные подключения замедляются по схеме 5, 10, 20, 40 и 60 секунд. Ближайшая отправка telemetry имеет приоритет, поэтому backoff не сдвигает её дальше заданного интервала. Старые агенты могут продолжать вызывать endpoint без параметра `wait`.

Ключ авторизации агента меняется из раздела **Обслуживание** в Web UI или Android. Новый token сохраняется в UCI, а прежний hash принимается сервером ещё 10 минут только для завершения запросов, начатых до ротации.

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

Команды выполняются только через авторизованный сервер и показываются в интерфейсах по реальным capabilities роутера. Повторная доставка команды не запускает действие второй раз: агент возвращает сохранённый terminal result по command id.

### Сегменты и VLAN

Агент передаёт фактические UCI-секции локальных интерфейсов, мостов и `bridge-vlan`. Web UI и Android не используют шаблонные адреса: после очередной telemetry показываются реальные IPv4, маска, DHCP-пул, bridge section, порты, STP, IGMP snooping и VLAN.

Из интерфейсов можно:

- создать отдельный LAN, Guest или IoT-сегмент;
- назначить физические порты в bridge;
- включить DHCP и выбрать политику доступа;
- создать или изменить Bridge VLAN 802.1Q;
- удалить только пользовательский сегмент; `lan`, `wan`, `wan6` и `loopback` защищены.

Перед применением сервер проверяет конфликты подсетей, DHCP-пулов, портов и VLAN. Агент создаёт UCI backup и откатывает изменение, если связь с сервером не восстановилась за контрольный интервал.

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
- роутер появился в БД, но не выходит на связь — installer до `0.16.1` мог сохранить старые `device_id` и token из `/etc/config/wrtmonitor`; запустите актуальный installer повторно с теми же параметрами.
