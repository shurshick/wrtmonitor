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

При polling agent получает команды и сервер переводит их в `sent`, заполняя `picked_at` и `retry_count`. Перед выполнением агент подтверждает статус `running`.

Если агент получил команду, но не подтвердил запуск за 45 секунд, delivery lease истекает и команда снова становится `queued`. Общий TTL команды остаётся пять минут.

После результата agent переводит команду в:

- `success`, если команда выполнена;
- `failed`, если команда завершилась ошибкой.

При этом сохраняются:

- `completed_at`
- `result`
- `last_error`

Повторная отправка финального результата идемпотентна: сохранённый terminal status не перезаписывается.

Перед опросом сервер помечает просроченные `queued`, `sent` и `running` команды как `expired`.

## Risk levels

- `level_1_readonly` - только чтение и диагностика;
- `level_2_safe_action` - безопасные служебные действия;
- `level_3_reversible_config` - изменение конфигурации или состояния, требующее подтверждения.

Для `requires_confirmation=true` backend требует `confirmed=true`.

## Валидация payload

Backend валидирует payload всех команд из `COMMAND_REGISTRY`: идентификаторы, IP/MAC, диапазоны портов, Wi-Fi, WAN/LAN, DHCP/DNS, системные действия и параметры агента.

Это защищает сервер от некорректных UI-форм и старых клиентов.

## Masking секретов

В истории команд и UI маскируются:

- `password`
- `wifi_password`
- `key`

Маскирование выполняется по metadata команды из `COMMAND_REGISTRY`.
