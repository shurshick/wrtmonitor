# Тестирование

## Автоматические проверки

GitHub Actions запускает PostgreSQL-тесты backend, E2E жизненного цикла команд и refresh-сессий, Ruff, ShellCheck, тесты OpenWrt agent и Android unit tests. Для релиза собирается и проверяется production-signed APK.

PostgreSQL backup восстанавливается во временную БД; CI проверяет `alembic_version` и таблицу владельца, после чего удаляет тестовую БД.

Chromium smoke-test авторизуется в Web UI, открывает список устройств и все разделы роутера на desktop и mobile viewport. Проверяются HTTP-ошибки, `Internal Server Error`, горизонтальное переполнение и реальный обмен данными с локальным xterm через WebSocket-брокер; скриншоты сохраняются в CI-артефакте `web-responsive-smoke`.

## Аппаратный E2E Web-терминала

Runner проверяет полный путь от Chromium до настоящего PTY роутера и обратно. Пароль передаётся только через переменную окружения:

```sh
export WRTMONITOR_E2E_PASSWORD='пароль владельца'
python scripts/terminal_hardware_e2e.py \
  --server https://monitor.example.ru \
  --username admin@example.com \
  --device HomeRouter
```

Успешный запуск создаёт `artifacts/terminal-hardware-e2e/result.json` и `terminal.png`. Тест не считается пройденным, пока xterm не получит уникальный маркер вместе с результатом `uname` из shell OpenWrt.

Runner отправляет Enter отдельным терминальным событием и тем самым проверяет тот же поток клавиатуры, которым пользуется человек в браузере. Отдельно проверяются переход в `connected`, вывод команды и закрытие PTY.

## Ручная регрессия

1. Откройте `/setup` на чистом сервере и создайте администратора.
2. Войдите через Web UI, откройте устройство, проверьте telemetry, Wi-Fi, сеть, историю команд и перезагрузку.
3. В Android укажите сервер, войдите, откройте устройство, переключите все вкладки, проверьте события сервера, отзыв сессии, «О приложении», выход и повторный вход.
4. На OpenWrt выполните `wrtmonitor-agent debug`, `wrtmonitor-agent debug-telemetry` и `wrtmonitor-agent send-now`.
5. Проверьте `/health` и `/health/config` через внешний HTTPS-адрес сервера.
6. После истечения access token убедитесь, что Android обновил сессию без повторного ввода пароля, а повторное использование старого refresh-token возвращает `401`.
7. Создайте PostgreSQL backup и выполните `python -m backend.app.backup_cli drill <файл>`.

Полный аппаратный прогон 93 команд выполняется отдельным runner. Порядок запуска,
требования к recovery-доступу и опубликованные отчёты описаны в
[real-router-testing.md](real-router-testing.md).

## Релизные артефакты

Перед публикацией формируются TrueNAS YAML, архив агента, Android APK и `SHA256SUMS.txt`. Контрольные суммы проверяются командой `sha256sum --check SHA256SUMS.txt`.
