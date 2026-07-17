# v0.3.0-rc6

Релиз закрывает основные долги стабилизации перед `v0.3.0`.

## Что изменилось

- Capabilities агента определяются по реальным утилитам, UCI-конфигурациям, сервисам и Wi-Fi-радио.
- Capability report v4 содержит причину недоступности каждой функции.
- Реализован полный цикл команды `queued -> sent -> running -> success/failed`.
- Зависшие при доставке команды повторно ставятся в очередь после истечения lease.
- Повторный финальный результат обрабатывается идемпотентно и не портит сохранённый статус.
- PostgreSQL E2E больше не пропускаются в CI и проверяют success, failure, retry и expiry.
- Chromium smoke-test проверяет все разделы Web UI на desktop и mobile viewport и сохраняет скриншоты.
- Android получает refresh token и автоматически восстанавливает сессию после истечения access token.
- Web UI и Android показывают причины отключённых capabilities.
- Android `versionCode` увеличен до `33`.

## Обновление

Агент `0.1.1-rc9` и последующие версии обновляются штатной командой обновления. После установки `rc6` убедитесь, что capability report имеет версию `4`.

Для сервера выполните redeploy образа `ghcr.io/shurshick/wrtmonitor:latest`. PostgreSQL volume сохраняется.

## Артефакты

- `wrtmonitor-android-v0.3.0-rc6-debug.apk`
- `wrtmonitor-openwrt-agent-v0.3.0-rc6.tar.gz`
- `wrtmonitor-truenas-v0.3.0-rc6.yaml`
- `SHA256SUMS.txt`
