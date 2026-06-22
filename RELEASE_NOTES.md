# v0.1.1-rc8-router-management-core

## Что вошло в релиз

- добавлен capability-aware слой между сервером, Web UI, Android и OpenWrt agent;
- backend получил единый `COMMAND_REGISTRY` с `risk_level`, `capability`, `requires_confirmation` и masking секретов;
- добавлена backend-валидация payload для `wifi.set_enabled`, `wifi.set_ssid`, `wifi.set_password`, `diagnostics.run`, `agent.set_auto_update`;
- latest telemetry теперь отдает нормализованные блоки `agent`, `wifi`, `network`;
- добавлен endpoint `GET /api/v1/devices/{device_id}/agent`;
- OpenWrt agent получил `capabilities`, `diagnostics`, `check-server`, `check-dns`, `check-route`, `check-wifi`, `check-dependencies`;
- перед изменением Wi-Fi agent создает backup `/etc/config/wireless` и умеет показывать список backup через `list-config-backups`;
- Web UI скрывает неподдерживаемые действия и показывает metadata команд, risk levels и результаты diagnostics;
- Android использует capabilities и новые telemetry-блоки для экранов устройства, Wi-Fi, сети и системы.

## Артефакты релиза

- `wrtmonitor-truenas-v0.1.1-rc8.yaml`
- `wrtmonitor-openwrt-agent-v0.1.1-rc8.tar.gz`
- `wrtmonitor-android-v0.1.1-rc8-debug.apk`
- `SHA256SUMS.txt`
