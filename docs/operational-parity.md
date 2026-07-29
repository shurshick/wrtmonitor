# Operational parity

`v0.27.0` использует единый реестр 90 команд для API, Web UI, Android и OpenWrt-агента.

## Проверка поверхностей

- `contracts/command-matrix.json` содержит capability, риск, post-condition, rollback и доступность операции;
- `contracts/surface-equivalents.json` описывает только осознанные пользовательские эквиваленты, когда имя API-операции отличается от имени команды агента;
- `scripts/generate_command_matrix.py` завершает CI ошибкой при отсутствии Web или Android операции;
- опасные действия сначала проходят серверный preview и используют одинаковое подтверждение.

## Фактические варианты

`GET /api/v1/devices/{device_id}/management-options` формирует варианты по последней telemetry конкретного роутера:

- сетевые интерфейсы, bridge и logical networks;
- firewall zones;
- Wi-Fi radios, текущий канал и поддерживаемые каналы;
- страны, маски и часовые пояса из серверного контракта.

Если роутер не передал объект, API не придумывает его. Интерфейс показывает пустое или unsupported-состояние.

## Android

Compose получает DTO/domain-модели через `RouterRepository`. Выбранный роутер, раздел, клиент и радиомодуль сохраняются через `rememberSaveable`. CI собирает test APK и запускает instrumented smoke tests на Android Emulator API 35.
