# WrtMonitor v0.35.13 — аварийная стабилизация

Тестовый релиз исправляет ошибки, найденные после серии `0.35.x`.

## Исправлено

- восстановлена реальная доставка PostgreSQL `LISTEN/NOTIFY` для SSE и long-poll;
- device token больше нельзя использовать для SSH-канала другого роутера;
- создание групп и отправка fleet-команд больше не завершаются внутренней ошибкой;
- fleet dispatch учитывает capabilities каждого роутера и сообщает, какие устройства были пропущены;
- Android APK получил новый `versionCode=87` и обновляется поверх предыдущей версии.

## Проверки

- unit и integration tests для realtime, SSH и fleet;
- полный backend/agent test suite;
- Android unit tests, lint и сборка APK.

Релиз остаётся тестовым и сначала публикуется как prerelease.
