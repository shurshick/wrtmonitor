# v0.1.1-rc2-architecture-refactor

## Backend

- `main.py` стал тонким ASGI entrypoint, создание приложения вынесено в `app_factory.py`.
- Web UI перенесён с HTML строк в Jinja2 templates; CSRF и security headers сохранены.
- Request schemas вынесены в `schemas/`, health endpoints зарегистрированы отдельным API router.

## Android

- `MainActivity` стал entrypoint; root UI перенесён в `WrtMonitorApp`.
- Добавлены `WrtMonitorApi`, `ApiResult`, DTO, `SessionStore` и domain `VersionComparator` с unit test.
- Android: `versionName 0.1.1-rc2`, `versionCode 18`.

## Compatibility

- API URLs, PostgreSQL data, agent protocol и TrueNAS deployment сохранены.
- APK ставится поверх rc1; agent version `0.1.1-rc2`.

## Known limitations

- Полное дробление всех Android экранов и всех API route modules продолжится следующим maintenance этапом.
- APK остаётся debug-сборкой; auto-update агента, firewall, DHCP и VPN не входят в rc2.
