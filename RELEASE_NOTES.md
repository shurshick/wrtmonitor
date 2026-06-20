# v0.1.1-rc2-architecture-refactor

## Изменения релиза

- Backend переведён на фабрику приложения: `main.py` стал тонким ASGI entrypoint, Web UI и API подключаются через отдельные routers.
- Логика авторизации, настройки сервера, аудита, команд и telemetry вынесена в `services/`.
- Web UI полностью использует Jinja2 templates и частичные шаблоны; CSS остаётся в статическом файле. CSRF и security headers сохранены.
- Android `MainActivity` стал минимальным entrypoint; добавлены API-слой, DTO, единое хранилище сессии, UI state и выделенные ключевые экраны.
- Сохранены API URLs, PostgreSQL-схема, протокол OpenWrt agent, установка APK поверх предыдущей версии и TrueNAS deployment.
- CI дополнен обязательной проверкой `ruff format --check` наряду с backend, agent и Android проверками.

## Артефакты

- `wrtmonitor-truenas-v0.1.1-rc2.yaml`
- `wrtmonitor-openwrt-agent-v0.1.1-rc2.tar.gz`
- `wrtmonitor-android-v0.1.1-rc2-debug.apk`
- `SHA256SUMS.txt`

Перед установкой артефактов проверяйте контрольные суммы из `SHA256SUMS.txt`.
