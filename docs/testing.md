# Тестирование

## Автоматические проверки

GitHub Actions запускает PostgreSQL-тесты backend, E2E жизненного цикла команд и refresh-сессий, Ruff, ShellCheck, тесты OpenWrt agent и Android unit tests. Для релиза собирается и проверяется production-signed APK.

PostgreSQL backup восстанавливается во временную БД; CI проверяет `alembic_version` и таблицу владельца, после чего удаляет тестовую БД.

Chromium smoke-test авторизуется в Web UI, открывает список устройств и все разделы роутера на desktop и mobile viewport. Проверяются HTTP-ошибки, `Internal Server Error` и горизонтальное переполнение; скриншоты сохраняются в CI-артефакте `web-responsive-smoke`.

## Ручная регрессия

1. Откройте `/setup` на чистом сервере и создайте администратора.
2. Войдите через Web UI, откройте устройство, проверьте telemetry, Wi-Fi, сеть, историю команд и перезагрузку.
3. В Android укажите сервер, войдите, откройте устройство, переключите все вкладки, проверьте события сервера, отзыв сессии, «О приложении», выход и повторный вход.
4. На OpenWrt выполните `wrtmonitor-agent debug`, `wrtmonitor-agent debug-telemetry` и `wrtmonitor-agent send-now`.
5. Проверьте `/health` и `/health/config` через внешний HTTPS-адрес сервера.
6. После истечения access token убедитесь, что Android обновил сессию без повторного ввода пароля, а повторное использование старого refresh-token возвращает `401`.
7. Создайте PostgreSQL backup и выполните `python -m backend.app.backup_cli drill <файл>`.

## Релизные артефакты

Перед публикацией формируются TrueNAS YAML, архив агента, Android APK и `SHA256SUMS.txt`. Контрольные суммы проверяются командой `sha256sum --check SHA256SUMS.txt`.
