# OpenWrt agent

Полная инструкция: [docs/openwrt-agent.md](../docs/openwrt-agent.md).

Agent работает только исходящими HTTPS-запросами к WrtMonitor. Открывать входящие порты на роутере не нужно.

## Быстрая установка с собственного сервера

После обновления WrtMonitor-образа агентные файлы доступны по адресу:

```text
https://monitor.example.ru/downloads/openwrt/
```

На роутере выполните:

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
  --admin-password 'your-password' \
  --name 'HomeRouter'
```

## Удаление

```sh
/etc/init.d/wrtmonitor stop 2>/dev/null || true
/etc/init.d/wrtmonitor disable 2>/dev/null || true
rm -f /usr/bin/wrtmonitor-agent
rm -f /etc/init.d/wrtmonitor
rm -f /etc/config/wrtmonitor
```

Запись устройства на сервере сохраняется как история. Новая установка создаст или повторно привяжет устройство к серверу.
