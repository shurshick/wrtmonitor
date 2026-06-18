# OpenWrt agent

Минимальный агент для `wrtmonitor`.

```sh
sh install-openwrt.sh --server https://monitor.example.ru --token DEVICE_TOKEN --name HomeRouter
```

Без параметров установщик спросит адрес сервера, device token и имя роутера в консоли.

Команды:

- `wrtmonitor-agent register`
- `wrtmonitor-agent send-now`
- `wrtmonitor-agent daemon`

Агент работает исходящими запросами к серверу, поэтому роутеру не нужен входящий порт из интернета.
