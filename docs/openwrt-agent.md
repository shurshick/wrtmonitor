# OpenWrt agent

`wrtmonitor-agent` регистрирует роутер, отправляет telemetry и получает только разрешённые команды. Он использует исходящие HTTPS-запросы к серверу, поэтому проброс портов на роутер не требуется.

## Требования

- OpenWrt с BusyBox `ash`;
- `curl`, `uci`, `ubus` и `jsonfilter`;
- доступ роутера к внешнему HTTPS-адресу WrtMonitor;
- созданный администратор сервера.

Проверьте и при необходимости установите зависимости:

```sh
command -v curl
command -v uci
command -v ubus
command -v jsonfilter

opkg update
opkg install curl jsonfilter
```

## Установка с собственного сервера

Это рекомендуемый способ для закрытых сетей и окружений без доступа к GitHub. После обновления контейнера WrtMonitor файлы агента автоматически доступны на вашем сервере:

```text
https://monitor.example.ru/downloads/openwrt/
```

Подставьте свой внешний HTTPS-домен и выполните на роутере:

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

Установщик получает короткоживущий admin token, создаёт отдельный `device_token`, записывает его в UCI и запускает сервис. Пароль администратора на роутере не сохраняется.

### Интерактивная установка

Если параметры не передавать, установщик задаст вопросы сам:

```sh
sh install-openwrt.sh
```

## Установка из GitHub Release

Используйте этот вариант, если сервер WrtMonitor ещё не обновлён или нужен фиксированный релизный архив. Скачайте архив со страницы нужного release, распакуйте его и запустите `install-openwrt.sh` с теми же параметрами.

```sh
cd /tmp
wget -O wrtmonitor-agent.tar.gz \
  https://github.com/shurshick/wrtmonitor/releases/download/v0.1.1-rc3-session-telemetry/wrtmonitor-openwrt-agent-v0.1.1-rc3.tar.gz
tar -xzf wrtmonitor-agent.tar.gz
sh install-openwrt.sh --server 'https://monitor.example.ru' --admin-user 'admin@example.com' --admin-password 'your-admin-password' --name 'HomeRouter'
```

## Проверка после установки

```sh
uci show wrtmonitor
/etc/init.d/wrtmonitor enabled
ps | grep wrtmonitor
wrtmonitor-agent version
wrtmonitor-agent send-now
logread | grep wrtmonitor | tail -30
```

Ожидается процесс `wrtmonitor-agent daemon`, а устройство должно обновиться в WebUI и Android. Для просмотра собранных данных используйте:

```sh
wrtmonitor-agent debug
wrtmonitor-agent debug-telemetry
wrtmonitor-agent debug-api
```

## Обновление агента с собственного сервера

Обновление сохраняет `device_id` и `device_token`, поэтому повторная авторизация администратором не нужна.

```sh
cd /tmp
/etc/init.d/wrtmonitor stop 2>/dev/null || true
BASE_URL='https://monitor.example.ru/downloads/openwrt'
wget -O wrtmonitor-agent "$BASE_URL/wrtmonitor-agent"
wget -O wrtmonitor.init "$BASE_URL/wrtmonitor.init"
chmod 0755 wrtmonitor-agent wrtmonitor.init
cp wrtmonitor-agent /usr/bin/wrtmonitor-agent
cp wrtmonitor.init /etc/init.d/wrtmonitor
/etc/init.d/wrtmonitor enable
/etc/init.d/wrtmonitor restart
wrtmonitor-agent send-now
```

Проверьте версию и лог:

```sh
wrtmonitor-agent version
logread | grep wrtmonitor | tail -30
```

## Полное удаление агента

Команда удаляет сервис, исполняемый файл и локальную конфигурацию. Telemetry и история команд на сервере остаются как исторические данные.

```sh
/etc/init.d/wrtmonitor stop 2>/dev/null || true
/etc/init.d/wrtmonitor disable 2>/dev/null || true
rm -f /usr/bin/wrtmonitor-agent
rm -f /etc/init.d/wrtmonitor
rm -f /etc/config/wrtmonitor
```

После удаления убедитесь, что процесс отсутствует:

```sh
ps | grep wrtmonitor
```

## Состав telemetry

Agent передаёт безопасный снимок состояния:

- uptime, load average, память и число процессов;
- CPU: модель и число ядер;
- место на overlay/корневом накопителе;
- температуру, если драйвер роутера предоставляет датчик;
- суммарные RX/TX-счётчики без MAC-адресов и содержимого трафика;
- board и firmware через `ubus`;
- статусы и IP-адреса интерфейсов;
- Wi-Fi radio, band, channel, SSID и состояние;
- расширенные `ubus` snapshots для совместимости с разными моделями OpenWrt.

MAC-адреса клиентов, пароли Wi-Fi и содержимое трафика agent не отправляет.

## Диагностика

Если нет telemetry:

```sh
wrtmonitor-agent send-now
logread | grep wrtmonitor | tail -30
uci get wrtmonitor.main.server_url
curl -i https://monitor.example.ru/health
```

Если в логе есть `jsonfilter is required`, установите `jsonfilter` через `opkg`.
