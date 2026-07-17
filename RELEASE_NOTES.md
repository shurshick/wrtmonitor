# v0.10.0

Релиз эксплуатации и безопасности сервера WrtMonitor.

## Изменения

- Access-token сокращён до 15 минут; refresh-сессии хранятся в PostgreSQL, ротируются при каждом обновлении и могут быть отозваны.
- Добавлены смена пароля владельца, список активных сессий и журнал аудита в Web UI и Android.
- Добавлены уведомления о недоступных роутерах, устаревших агентах и ошибках команд.
- Добавлены создание, проверка, контрольное восстановление и восстановление PostgreSQL backup.
- В TrueNAS YAML добавлен постоянный volume `/backups`.
- GitHub Release теперь содержит production-signed Android APK вместо debug APK.
- CI проверяет миграции, refresh rotation, PostgreSQL disaster-recovery drill, Web UI на desktop/mobile и подпись APK.
- Android `versionCode` увеличен до `41`.

## Обновление

- TrueNAS: выполните **Apps -> WrtMonitor -> Edit -> Save**, чтобы заново скачать `ghcr.io/shurshick/wrtmonitor:latest`.
- База обновится миграцией `0005_user_sessions`; существующие устройства и telemetry сохраняются.
- Агент: автообновление установит `0.10.0` поверх `0.9.0`.
- Android: из-за перехода с тестового debug-ключа на production-подпись удалите старый debug APK и один раз установите `wrtmonitor-android-v0.10.0.apk` начисто. Дальнейшие версии будут обновляться поверх `v0.10.0`.

## Артефакты

- `wrtmonitor-android-v0.10.0.apk`
- `wrtmonitor-openwrt-agent-v0.10.0.tar.gz`
- `wrtmonitor-truenas-v0.10.0.yaml`
- `SHA256SUMS.txt`
- `agent-version.txt`
