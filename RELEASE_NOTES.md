# v0.1.0-test.15 — Stability, Web UI and TrueNAS latest

## Android

- Исправлено падение после первого входа: adaptive launcher icon больше не используется как неподдерживаемый Compose painter.
- Версия приложения: `0.1.0-test.15`, `versionCode 15`.

## Web UI

- Список устройств получил обновлённый интерфейс и переход на страницу роутера.
- Страница устройства показывает telemetry, Wi-Fi radios, сетевые интерфейсы, системные данные и историю команд.
- Из Web UI доступны безопасные команды: включение/выключение Wi-Fi, смена SSID, запрос сетевых интерфейсов и перезагрузка с подтверждением.

## TrueNAS

- TrueNAS YAML переведён на `ghcr.io/shurshick/wrtmonitor:latest`.
- Добавлен `pull_policy: always` для получения нового образа при redeploy.
- Инструкции поясняют обязательный ручной redeploy в TrueNAS: работающий контейнер сам не заменяется.

## Артефакты

- Docker image: `ghcr.io/shurshick/wrtmonitor:latest` и `ghcr.io/shurshick/wrtmonitor:0.1.0-test.15`.
- TrueNAS YAML: `wrtmonitor-truenas-v0.1.0-test.15.yaml`.
- Android APK: `wrtmonitor-android-v0.1.0-test.15-debug.apk`.
- OpenWrt agent: `wrtmonitor-openwrt-agent-v0.1.0-test.15.tar.gz`.
- Checksums: `SHA256SUMS.txt`.
