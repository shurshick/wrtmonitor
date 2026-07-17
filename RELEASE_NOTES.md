# v0.3.0

Первый стабильный выпуск линии `0.3` для сервера, OpenWrt-агента и Android.

## Что изменилось относительно rc6

- Зафиксирована совместимость сервера, агента и Android на capability report schema v4.
- Подтверждены PostgreSQL E2E, полный lifecycle команд и адаптивный Chromium smoke-test.
- GitHub Actions переведены на актуальный Node 24 runtime.
- Android `versionCode` увеличен до `34`, APK устанавливается поверх предыдущих RC.
- Документация и инструкции синхронизированы со стабильным тегом.

## Обновление

- Сервер: выполните redeploy `ghcr.io/shurshick/wrtmonitor:latest`.
- Агент: используйте кнопку проверки обновления или штатную команду agent update.
- Android: установите новый APK поверх предыдущей версии.

PostgreSQL volume при обновлении контейнера сохраняется.

## Артефакты

- `wrtmonitor-android-v0.3.0-debug.apk`
- `wrtmonitor-openwrt-agent-v0.3.0.tar.gz`
- `wrtmonitor-truenas-v0.3.0.yaml`
- `SHA256SUMS.txt`
