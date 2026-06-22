# Жизненный цикл команд

Android, API и Web UI создают только команды из `COMMAND_REGISTRY`.

Новая команда получает:

- статус `queued`;
- `source` (`api` или `web`);
- `expires_at`;
- `risk_level`;
- `capability`;
- masked `payload`.

## Переходы статусов

Поддерживаются статусы:

- `queued`
- `sent`
- `running`
- `success`
- `failed`
- `expired`
- `cancelled`

При polling agent получает команды и сервер переводит их в `sent`, заполняя `picked_at` и `retry_count`.

После результата agent переводит команду в:

- `success`, если команда выполнена;
- `failed`, если команда завершилась ошибкой.

При этом сохраняются:

- `completed_at`
- `result`
- `last_error`

Перед опросом сервер помечает просроченные `queued`, `sent` и `running` команды как `expired`.

## Risk levels

- `level_1_readonly` - только чтение и диагностика;
- `level_2_safe_action` - безопасные служебные действия;
- `level_3_reversible_config` - изменение конфигурации или состояния, требующее подтверждения.

Для `requires_confirmation=true` backend требует `confirmed=true`.

## Валидация payload

В `rc8` backend валидирует:

- `wifi.set_enabled`
- `wifi.set_ssid`
- `wifi.set_password`
- `diagnostics.run`
- `agent.set_auto_update`

Это защищает сервер от некорректных UI-форм и старых клиентов.

## Masking секретов

В истории команд и UI маскируются:

- `password`
- `wifi_password`
- `key`

Маскирование выполняется по metadata команды из `COMMAND_REGISTRY`.
