# v0.7.0

Релиз маршрутизации и сетевого периметра.

## Изменения

- IPv6, RA и DHCPv6, статические IPv4/IPv6-маршруты.
- Multi-WAN с приоритетом и failover через `mwan3`.
- DDNS и UPnP с отображением активных динамических пробросов.
- Управление зонами, транзитом и правилами firewall.
- Расширенная perimeter-телеметрия и полный паритет Web UI/Android.
- Capability report обновлён до schema v8; Android `versionCode` увеличен до `38`.
- Все изменения конфигурации защищены транзакционным backup и rollback.

## Обновление

- Сервер: выполните redeploy `ghcr.io/shurshick/wrtmonitor:latest`.
- Агент: автообновление установит `0.7.0`; после обновления проверьте `wrtmonitor-agent capabilities --json`.
- Android: установите `wrtmonitor-android-v0.7.0-debug.apk` поверх предыдущей версии.

PostgreSQL volume при обновлении контейнера сохраняется. Новая миграция БД этому релизу не требуется.

## Артефакты

- `wrtmonitor-android-v0.7.0-debug.apk`
- `wrtmonitor-openwrt-agent-v0.7.0.tar.gz`
- `wrtmonitor-truenas-v0.7.0.yaml`
- `SHA256SUMS.txt`
