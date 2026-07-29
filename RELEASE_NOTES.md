# v0.27.0-operational-parity

Тестовый релиз закрепляет единый набор операций и фактических параметров управления в Web UI и Android.

## Изменения

- все 90 команд доступны через эквивалентные пользовательские операции Web UI и Android;
- новый management-options API возвращает варианты выбора из текущей telemetry роутера;
- Wi-Fi каналы формируются по возможностям выбранного радиомодуля, а не по встроенному списку;
- Android-экраны управления обращаются к серверу через Repository и сохраняют выбранное состояние;
- инструментальные Android-тесты запускаются на эмуляторе как обязательный release gate.

## Проверка

- backend, contract и API tests;
- OpenWrt static tests, shell syntax и command harness;
- Android unit, lint и emulator UI tests;
- command matrix и architecture validators.
