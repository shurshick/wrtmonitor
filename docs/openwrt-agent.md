# OpenWrt agent

Agent устанавливается на роутер и работает как клиент сервера.

Функции:

- регистрация устройства;
- отправка heartbeat;
- отправка telemetry;
- получение команд;
- выполнение allowlist-команд через `uci`, `wifi`, `reboot`, `ubus`.

Пример установки:

```sh
sh install-openwrt.sh \
  --server https://monitor.example.ru \
  --token DEVICE_TOKEN \
  --name HomeRouter
```

Команды управления должны быть ограничены и логироваться.
