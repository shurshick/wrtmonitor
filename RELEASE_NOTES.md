# v0.10.4

Исправление Web UI-авторизации при работе через HTTPS и локальный HTTP.

## Изменения

- Web UI распознаёт HTTPS за reverse proxy по `X-Forwarded-Proto`.
- Вход через локальный HTTP больше не заканчивается молчаливым возвратом на форму.
- При обязательной защищённой cookie интерфейс показывает ссылку на настроенный HTTPS-адрес.
- Если браузер блокирует session cookie, Web UI показывает точную причину после входа.
- Логин очищается от случайных пробелов одинаково для Web UI и Android API.
- Добавлены тесты HTTPS proxy, `Secure`/`HttpOnly`/`SameSite` cookie и запрета небезопасного HTTP.
- Android `versionCode` увеличен до `45`.

## Обновление

Обновите сервер через TrueNAS redeploy: **Apps -> WrtMonitor -> Edit -> Save**.
Миграция БД не требуется.

Для обычной установки открывайте Web UI по внешнему HTTPS-адресу. Локальный HTTP
доступ допускается только при явном `WRTMONITOR_ALLOW_INSECURE_LOCAL=true`.

## Артефакты

- `wrtmonitor-android-v0.10.4.apk`
- `wrtmonitor-openwrt-agent-v0.10.4.tar.gz`
- `wrtmonitor-truenas-v0.10.4.yaml`
- `SHA256SUMS.txt`
- `agent-version.txt`
