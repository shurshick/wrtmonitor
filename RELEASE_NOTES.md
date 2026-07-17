# v0.8.0

Релиз VPN и policy routing.

## Изменения

- WireGuard server/client: интерфейсы, peer, ключи, AllowedIPs, endpoint и keepalive.
- Безопасный экспорт peer-конфигурации без передачи приватного ключа сервера.
- Импорт и удаление OpenVPN client profiles.
- Policy-based routing по адресу клиента, подсети и назначению через `pbr`.
- Статусы туннелей, handshake и счётчики RX/TX в Web UI и Android.
- Capability report обновлён до schema v9; Android `versionCode` увеличен до `39`.
- VPN-конфигурации защищены transaction backup/rollback, секреты скрыты в preview и журнале.

## Обновление

- Сервер: выполните redeploy `ghcr.io/shurshick/wrtmonitor:latest`.
- Агент: автообновление установит `0.8.0`; для WireGuard/OpenVPN/PBR установите соответствующие пакеты OpenWrt.
- Android: установите `wrtmonitor-android-v0.8.0-debug.apk` поверх предыдущей версии.

PostgreSQL volume при обновлении контейнера сохраняется. Новая миграция БД этому релизу не требуется.

## Артефакты

- `wrtmonitor-android-v0.8.0-debug.apk`
- `wrtmonitor-openwrt-agent-v0.8.0.tar.gz`
- `wrtmonitor-truenas-v0.8.0.yaml`
- `SHA256SUMS.txt`
