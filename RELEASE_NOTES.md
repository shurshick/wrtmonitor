# WrtMonitor v0.37.0 — аппаратная идентификация

Тестовый релиз создаёт нормальную основу для отображения процессоров и датчиков OpenWrt-устройств.

## Изменено

- агент читает модель и совместимость платы из Device Tree, target OpenWrt и архитектуру системы;
- CPU telemetry содержит наблюдаемую модель, ядра и частоты `cpufreq`, включая данные по каждому ядру;
- все доступные `thermal_zone` и `hwmon` датчики передаются отдельными записями с собственным типом и меткой;
- PostgreSQL получил каталог аппаратных профилей, observed identity и 45-дневную историю температуры;
- первый профиль каталога описывает Netis NX31, MediaTek MT7981B и Arm Cortex-A53 по данным OpenWrt;
- Web UI и Android показывают модель SoC, CPU, архитектуру, текущую/максимальную частоту и min/max датчиков;
- каталог не подменяет значения агента: неизвестное железо остаётся неизвестным, неподдерживаемое измерение не превращается в ноль.

## Проверки

- backend и OpenWrt-agent unit/contract tests;
- PostgreSQL migration и E2E сопоставления Netis NX31 с историей нескольких датчиков;
- Android Kotlin compile, unit/lint/release build в CI;
- shell syntax, shellcheck, agent harness и browser smoke.

Android `versionCode`: `93`.
