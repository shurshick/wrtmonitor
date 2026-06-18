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

Если `--server`, `--token` или `--name` не переданы, установщик спросит значения в консоли. Имя роутера можно оставить пустым.

Команды управления должны быть ограничены и логироваться.

Текущий allowlist:

- `router.reboot`;
- `wifi.status`;
- `wifi.set_enabled`;
- `wifi.set_ssid`;
- `network.interfaces`.

Произвольный `shell.exec` и произвольный `uci.apply` не поддерживаются.
