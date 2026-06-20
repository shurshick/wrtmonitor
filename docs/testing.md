# Тестирование

## Автоматические проверки

GitHub Actions запускает PostgreSQL-тесты backend, Ruff, ShellCheck, статический тест OpenWrt agent и Android unit tests с debug-сборкой APK.

## Ручная регрессия

1. Откройте `/setup` на чистом сервере и создайте администратора.
2. Войдите через Web UI, откройте устройство, проверьте telemetry, Wi-Fi, сеть, историю команд и перезагрузку.
3. В Android укажите сервер, войдите, откройте устройство, переключите все вкладки, проверьте «О приложении», выход и повторный вход.
4. На OpenWrt выполните `wrtmonitor-agent debug`, `wrtmonitor-agent debug-telemetry` и `wrtmonitor-agent send-now`.
5. Проверьте `/health` и `/health/config` через внешний HTTPS-адрес сервера.

## Релизные артефакты

Перед публикацией формируются TrueNAS YAML, архив агента, Android APK и `SHA256SUMS.txt`. Контрольные суммы проверяются командой `sha256sum --check SHA256SUMS.txt`.
