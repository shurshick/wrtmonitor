# Release Notes

## v0.1.0-test.11 — agent stability

Релиз закрепляет telemetry-контур `v0.1.0-test.10` и делает OpenWrt agent/backend надёжнее для дальнейших тестов.

Главное:

- OpenWrt agent проверяется через `sh -n`, shellcheck и agent smoke tests.
- Критичные JSON-поля в agent читаются через `jsonfilter`, а не regex.
- Wi-Fi telemetry готова к multi-radio конфигурациям.
- Сервер не стартует с дефолтным JWT secret или дефолтным паролем PostgreSQL.
- API последней телеметрии возвращает `age_seconds`, `is_stale` и `source`.
- Сервер хранит последние 100 telemetry snapshots на устройство.
- Android экран устройства показывает основные telemetry-поля без raw JSON как основного UI.

Артефакты:

- Docker image: `ghcr.io/shurshick/wrtmonitor:0.1.0-test.11`;
- TrueNAS YAML: `wrtmonitor-truenas-v0.1.0-test.11.yaml`;
- Android APK: `wrtmonitor-android-v0.1.0-test.11-debug.apk`;
- OpenWrt agent: `wrtmonitor-openwrt-agent-v0.1.0-test.11.tar.gz`;
- checksums: `SHA256SUMS.txt`.

Обновление с `v0.1.0-test.10`:

- PostgreSQL volume удалять не нужно.
- Замените `WRTMONITOR_JWT_SECRET`, если он дефолтный или короткий.
- Замените `POSTGRES_PASSWORD` и пароль в `WRTMONITOR_DATABASE_URL`, если они начинаются с `change-me`.
- Обновите OpenWrt agent.
- Обновите Android APK.
