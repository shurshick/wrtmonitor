# Changelog

## v0.1.0-test.11

- Стабилизирован OpenWrt agent для BusyBox `ash`.
- Исправлена установка и обновление агента на OpenWrt без зависимости от команды `install`.
- Добавлен разбор ответов API через `jsonfilter`.
- Исправлена отправка telemetry из агента: JSON больше не ломается на вложенных данных Wi-Fi.
- Добавлена структура multi-radio Wi-Fi telemetry.
- Сервер отклоняет запуск с дефолтными паролями базы данных.
- API последней телеметрии возвращает `age_seconds`, `is_stale` и `source`.
- Добавлено ограничение хранения telemetry: последние 100 snapshots на устройство.
- Добавлены backend E2E tests и smoke tests для агента.
- Улучшен Android-экран устройства с отображением telemetry.
- Обновлены release assets: TrueNAS YAML, OpenWrt agent archive, Android debug APK и `SHA256SUMS.txt`.

## v0.1.0-test.10

- Добавлен первый end-to-end telemetry flow.
- Добавлен API последней телеметрии.
- Добавлен Android-экран устройства.
- Добавлена защита от дефолтных JWT-секретов.
