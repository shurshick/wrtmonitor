# OpenWrt agent

Краткая инструкция для установки агента на роутер.

Полная инструкция: [`docs/openwrt-agent.md`](../docs/openwrt-agent.md).

## Установка

```sh
cd /tmp
wget -O wrtmonitor-openwrt-agent-v0.1.0-test.11.tar.gz \
  https://github.com/shurshick/wrtmonitor/releases/download/v0.1.0-test.11/wrtmonitor-openwrt-agent-v0.1.0-test.11.tar.gz
tar -xzf wrtmonitor-openwrt-agent-v0.1.0-test.11.tar.gz
sh install-openwrt.sh \
  --server https://monitor.example.ru \
  --admin-user admin@example.com \
  --admin-password 'your-admin-password' \
  --name 'HomeRouter'
```

## Обновление

```sh
cd /tmp
/etc/init.d/wrtmonitor stop 2>/dev/null
rm -f wrtmonitor-agent install-openwrt.sh wrtmonitor.init wrtmonitor.config
wget -O wrtmonitor-openwrt-agent-v0.1.0-test.11.tar.gz \
  https://github.com/shurshick/wrtmonitor/releases/download/v0.1.0-test.11/wrtmonitor-openwrt-agent-v0.1.0-test.11.tar.gz
tar -xzf wrtmonitor-openwrt-agent-v0.1.0-test.11.tar.gz
cp wrtmonitor-agent /usr/bin/wrtmonitor-agent
chmod 0755 /usr/bin/wrtmonitor-agent
cp wrtmonitor.init /etc/init.d/wrtmonitor
chmod 0755 /etc/init.d/wrtmonitor
/etc/init.d/wrtmonitor enable
/etc/init.d/wrtmonitor restart
wrtmonitor-agent send-now
```

## Проверка

```sh
uci show wrtmonitor
ps | grep wrtmonitor
logread | grep wrtmonitor | tail -20
```

Агент работает исходящими запросами к серверу. Входящий порт на роутере открывать не нужно.
