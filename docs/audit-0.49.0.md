# Runtime-сертификация 0.49.0

## Причина

После разделения агента в `0.48.0` автоматические тесты подтверждали синтаксис и контракты, но часть аппаратных post-condition была слишком слабой. Статус `online` мог остаться от старой telemetry, а terminal E2E не проверял resize и повторное подключение.

## Обязательные доказательства

- `router.reboot`: новый kernel `boot_id` и новая отметка telemetry;
- `agent.disconnect`: UCI `enabled=0`, daemon отсутствует, после recovery приходит новая telemetry;
- `agent.update` и `agent.rollback`: процесс работает и зафиксирована фактическая версия;
- `agent.ssh_session`: ввод прошёл через PTY, `stty size` совпал с xterm, reconnect создал новый session ID, `exit` закрыл сессию;
- все 94 команды имеют `pass` либо честный `not_applicable` по отсутствующей capability.

## Результат

Отчёты Netis NX31 и OpenWrt x86 проверяются `runtime_validation_report.py`. Любое отсутствующее runtime-доказательство завершает gate ошибкой.
