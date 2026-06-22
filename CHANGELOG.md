# Changelog

## v0.1.1-rc8-router-management-core

- Добавлены `agent capabilities`, нормализованные `agent/wifi/network` блоки telemetry и endpoint `GET /api/v1/devices/{device_id}/agent`.
- Backend получил `COMMAND_REGISTRY`, risk levels, masking секретов и валидацию payload для управляющих команд.
- OpenWrt agent получил diagnostics CLI, capability report и backup `wireless` перед изменением Wi-Fi.
- Web UI и Android стали capability-aware и показывают diagnostics и metadata команд.

## v0.1.1-rc7-agent-update-safety

- Добавлено безопасное автообновление OpenWrt agent через `SHA256SUMS.txt`.
- Добавлены backup, rollback, защита от downgrade и статус обновления в Web UI и Android.
- Удаление устройства из списка закреплено как soft-archive только для `disabled` устройств.

## v0.1.1-rc2-architecture-refactor

- Вынесены factory, route layer, Jinja2 templates и schemas backend.
- Добавлены Android API/data/domain layers и unit test сравнения версий.

## v0.1.1-rc1 - Real Router Validation and Control Polish

- Добавлены API истории команд, agent version и support bundle.
- Добавлен чек-лист валидации на реальном OpenWrt-роутере.
