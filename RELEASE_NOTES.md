# v0.26.0-architecture-split

Тестовый архитектурный релиз разбивает сервер, агент и Android на подсистемы без изменения пользовательского контракта 90 команд.

## Изменения

- backend commands, telemetry и Web routes разделены по предметным модулям;
- command и telemetry shell-код агента разделён по тем же подсистемам;
- API request/result и reliability policy получили строгие типы;
- Android получил Repository и ViewModel для списка устройств и live telemetry;
- transport JSON больше не разбирается внутри Compose;
- архитектурная проверка включена в CI.

## Проверка

- backend test suite и ruff;
- OpenWrt static tests, shell syntax и command harness;
- Android compile и unit tests;
- contract, command matrix и architecture validators.
