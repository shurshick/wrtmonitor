# v0.6.0

Релиз расширенного управления Wi-Fi.

## Изменения

- Несколько SSID на каждом radio: создание, изменение, отключение и удаление.
- Настройка канала, ширины, страны и мощности передатчика одной транзакционной командой.
- Расписание активности Wi-Fi с проверкой внутри рабочего цикла агента.
- Изоляция клиентов, 802.11r/k/v и Mesh 802.11s при наличии поддержки в сборке OpenWrt.
- Телеметрия подключённых Wi-Fi-клиентов: signal, noise, RX/TX bitrate, airtime и время подключения.
- Полный набор новых действий доступен в Web UI и Android.
- Capability report обновлён до schema v7; Android `versionCode` увеличен до `37`.

## Обновление

- Сервер: выполните redeploy `ghcr.io/shurshick/wrtmonitor:latest`.
- Агент: автообновление установит `0.6.0`; после обновления проверьте `wrtmonitor-agent capabilities --json`.
- Android: установите `wrtmonitor-android-v0.6.0-debug.apk` поверх предыдущей версии.

PostgreSQL volume при обновлении контейнера сохраняется. Новая миграция БД этому релизу не требуется.

## Артефакты

- `wrtmonitor-android-v0.6.0-debug.apk`
- `wrtmonitor-openwrt-agent-v0.6.0.tar.gz`
- `wrtmonitor-truenas-v0.6.0.yaml`
- `SHA256SUMS.txt`
