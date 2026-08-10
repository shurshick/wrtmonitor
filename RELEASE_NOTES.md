# WrtMonitor v0.38.0 — Hardware Intelligence

Тестовый релиз превращает сырые аппаратные поля в проверяемую и честную модель оборудования.

## Изменено

- неизвестная плата получает наблюдаемый профиль по точным Device Tree/OpenWrt identifiers; совпадение по общему SoC не используется;
- встроенный каталог содержит проверенные профили Netis NX31, Banana Pi BPI-R3, Xiaomi AX3600 и FriendlyElec NanoPi R5S;
- сервер явно сообщает, является профиль проверенным или автоматически изученным;
- реальные Netis NX31 датчики нормализуются в SoC, Wi-Fi 2.4 ГГц и Wi-Fi 5 ГГц, дубликат температуры SoC не засоряет интерфейс;
- warning/critical limits читаются из `thermal`/`hwmon`; статус без доступного порога остаётся неизвестным;
- при поддержке ядром передаётся `thermal_pressure` и состояние троттлинга;
- отдельный раздел «Оборудование» добавлен в Web UI и Android.

## Проверки

- backend unit/contract tests и PostgreSQL schema E2E;
- shell syntax и agent telemetry contract;
- Android Kotlin compile, unit tests, lint и APK build;
- Web UI smoke и релизная проверка версии.

Android `versionCode`: `94`.
