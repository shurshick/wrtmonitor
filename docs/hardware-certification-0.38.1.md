# Аппаратная сертификация 0.38.1

Проверка выполнена на реальных тестовых стендах. Значения ниже получены из OpenWrt, sysfs и telemetry агента, а не из каталожных предположений.

## Netis NX31

- OpenWrt 25.12.4, target `mediatek/filogic`;
- Device Tree: `netis,nx31`, `mediatek,mt7981`;
- архитектура `aarch64`, 2 ядра Arm Cortex-A53;
- SoC MediaTek MT7981B определён проверенным профилем;
- thermal: `cpu-thermal`, текущая температура передаётся из sysfs;
- trip points: critical 125 C, hot 120 C, active 115/85/60 C;
- hwmon: SoC и радиомодули MediaTek MT7915 2.4/5 ГГц;
- пороги hwmon передаются как их сообщает ядро, без исправления или догадок сервера.

## OpenWrt x86

- OpenWrt 22.03.5, target `x86/64`;
- модель `innotek GmbH VirtualBox`;
- архитектура `x86_64`, гостевой системе доступно 2 ядра;
- наблюдаемая строка CPU сохраняется без подмены моделью хоста;
- thermal и hwmon в гостевой системе отсутствуют;
- Web UI, Android и API показывают `unsupported`, температура не вычисляется.

## Неизвестная модель

Автообучение создаёт наблюдаемый профиль только по устойчивому сочетанию board name, compatible, model и target. Совпадение по общему SoC или target не считается идентификацией модели. Аппаратный отчёт доступен по `GET /api/v1/devices/{device_id}/hardware/report` и в разделе «Оборудование» Web UI.
