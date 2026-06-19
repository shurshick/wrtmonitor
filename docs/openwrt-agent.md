# OpenWrt agent

OpenWrt agent — shell-клиент `wrtmonitor`, который устанавливается на роутер, регистрирует устройство на сервере, отправляет telemetry и периодически забирает разрешённые команды.

Агент работает исходящими HTTPS-запросами к серверу. Входящий порт на роутере открывать не нужно.

## Требования

- OpenWrt с BusyBox `ash`;
- `curl`;
- `uci`;
- `jsonfilter`;
- доступ роутера к серверу `wrtmonitor`;
- созданный администратор на сервере.

`jsonfilter` нужен для безопасного чтения JSON-ответов сервера. Если его нет, агент пишет ошибку в `logread` и не выполняет команды.

Проверьте пакеты на роутере:

```sh
command -v curl
command -v uci
command -v jsonfilter
```

Если `jsonfilter` отсутствует:

```sh
opkg update
opkg install jsonfilter
```

## Установка с нуля

Перейдите во временную директорию:

```sh
cd /tmp
```

Скачайте архив агента из актуального релиза:

```sh
wget -O wrtmonitor-openwrt-agent-v0.1.0-test.11.tar.gz \
  https://github.com/shurshick/wrtmonitor/releases/download/v0.1.0-test.11/wrtmonitor-openwrt-agent-v0.1.0-test.11.tar.gz
```

Распакуйте архив:

```sh
tar -xzf wrtmonitor-openwrt-agent-v0.1.0-test.11.tar.gz
```

Запустите установщик:

```sh
sh install-openwrt.sh \
  --server https://monitor.example.ru \
  --admin-user admin@example.com \
  --admin-password 'your-admin-password' \
  --name 'HomeRouter'
```

Замените:

- `https://monitor.example.ru` на внешний HTTPS-адрес сервера;
- `admin@example.com` на логин администратора, созданного на `/setup`;
- `your-admin-password` на пароль администратора;
- `HomeRouter` на понятное имя роутера.

Что делает установщик:

- логинится на сервер через `/api/v1/auth/login`;
- вызывает `/api/v1/devices/provision`;
- получает отдельный `device_token`;
- сохраняет настройки в UCI `/etc/config/wrtmonitor`;
- устанавливает `/usr/bin/wrtmonitor-agent`;
- устанавливает init-скрипт `/etc/init.d/wrtmonitor`;
- включает автозапуск;
- запускает сервис.

Пароль администратора на роутере не сохраняется. На роутере хранится только `device_token`.

## Интерактивная установка

Можно запустить установщик без параметров:

```sh
sh install-openwrt.sh
```

Он спросит:

- адрес сервера;
- логин администратора;
- пароль администратора;
- имя роутера;
- интервал отправки telemetry.

## Проверка после установки

Проверьте конфигурацию:

```sh
uci show wrtmonitor
```

Ожидаемые поля:

```text
wrtmonitor.main.server_url='https://monitor.example.ru'
wrtmonitor.main.device_id='...'
wrtmonitor.main.device_token='...'
wrtmonitor.main.name='HomeRouter'
wrtmonitor.main.interval='60'
```

Проверьте автозапуск:

```sh
/etc/init.d/wrtmonitor enabled
```

Проверьте процесс:

```sh
ps | grep wrtmonitor
```

Отправьте telemetry вручную:

```sh
wrtmonitor-agent send-now
```

Посмотрите лог:

```sh
logread | grep wrtmonitor | tail -20
```

На сервере устройство должно появиться в `/devices`, а в Android — в списке роутеров. На экране устройства должна появиться последняя telemetry.

## Обновление агента

Обновление не требует повторной регистрации, если в UCI уже сохранены `device_id` и `device_token`.

Остановите сервис:

```sh
/etc/init.d/wrtmonitor stop 2>/dev/null
```

Скачайте новый архив:

```sh
cd /tmp
rm -f wrtmonitor-agent install-openwrt.sh wrtmonitor.init wrtmonitor.config
wget -O wrtmonitor-openwrt-agent-v0.1.0-test.11.tar.gz \
  https://github.com/shurshick/wrtmonitor/releases/download/v0.1.0-test.11/wrtmonitor-openwrt-agent-v0.1.0-test.11.tar.gz
tar -xzf wrtmonitor-openwrt-agent-v0.1.0-test.11.tar.gz
```

Замените скрипт агента:

```sh
cp wrtmonitor-agent /usr/bin/wrtmonitor-agent
chmod 0755 /usr/bin/wrtmonitor-agent
```

Обновите init-скрипт:

```sh
cp wrtmonitor.init /etc/init.d/wrtmonitor
chmod 0755 /etc/init.d/wrtmonitor
```

Запустите сервис:

```sh
/etc/init.d/wrtmonitor enable
/etc/init.d/wrtmonitor restart
```

Проверьте отправку:

```sh
wrtmonitor-agent send-now
logread | grep wrtmonitor | tail -20
```

Если `send-now` завершился без ошибки и новых `telemetry failed` в логе нет, обновление прошло успешно.

## Полная переустановка агента

Если нужно заново привязать роутер к серверу:

```sh
/etc/init.d/wrtmonitor stop 2>/dev/null
rm -f /usr/bin/wrtmonitor-agent
rm -f /etc/init.d/wrtmonitor
rm -f /etc/config/wrtmonitor
```

После этого выполните установку с нуля.

## Telemetry

Агент отправляет:

- `system`: uptime, load average, память, `ubus system info`;
- `board`: `ubus system board`;
- `network`: `ubus network.interface dump`;
- `wifi`: multi-radio snapshot из UCI `wireless`.

Wi-Fi telemetry имеет структуру:

```json
{
  "available": true,
  "radios": [
    {
      "name": "radio0",
      "up": true,
      "band": "2g",
      "channel": "6",
      "ssid": ["Home"],
      "encryption": "psk2"
    }
  ]
}
```

Если `ubus`, `wifi` или часть UCI-данных недоступны, агент должен отправить частичный snapshot, а не падать.

## Команды управления

Агент выполняет только команды из allowlist:

- `router.reboot`;
- `wifi.status`;
- `wifi.set_enabled`;
- `wifi.set_ssid`;
- `network.interfaces`.

Команды `wifi.set_enabled` и `wifi.set_ssid` поддерживают параметры `radio` и `iface`. Если они не переданы, используется первый radio/iface для обратной совместимости.

Произвольные `shell.exec` и `uci.apply` не поддерживаются.

## Диагностика

Сервис не запущен:

```sh
/etc/init.d/wrtmonitor restart
ps | grep wrtmonitor
```

Нет telemetry:

```sh
wrtmonitor-agent send-now
logread | grep wrtmonitor | tail -30
```

Проверить URL и токен:

```sh
uci get wrtmonitor.main.server_url
uci get wrtmonitor.main.device_id
uci get wrtmonitor.main.device_token
```

Проверить доступность сервера:

```sh
curl -i https://monitor.example.ru/health
```

Если в логе есть `jsonfilter is required`, установите пакет:

```sh
opkg update
opkg install jsonfilter
```
